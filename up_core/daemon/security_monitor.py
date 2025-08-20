import os
import re
import time
import logging
import threading
import subprocess
import socket
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

# Global variables
_monitor_thread = None
_stop_event = threading.Event()
_check_interval = 3600  # 1 hour by default
_security_issues = []

def start():
    """Start the security monitoring thread"""
    global _monitor_thread, _stop_event
    
    if _monitor_thread and _monitor_thread.is_alive():
        logger.info("Security monitoring already running")
        return
    
    _stop_event.clear()
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _monitor_thread.start()
    logger.info("Security monitoring started")

def stop():
    """Stop the security monitoring thread"""
    global _monitor_thread, _stop_event
    
    if _monitor_thread and _monitor_thread.is_alive():
        logger.info("Stopping security monitoring")
        _stop_event.set()
        _monitor_thread.join(timeout=5)
        if _monitor_thread.is_alive():
            logger.warning("Security monitoring thread did not stop gracefully")
        else:
            logger.info("Security monitoring stopped")
    else:
        logger.info("Security monitoring not running")

def check_security():
    """Run all security checks and return issues"""
    global _security_issues
    
    issues = []
    
    # Check for failed login attempts
    issues.extend(_check_failed_logins())
    
    # Check for unauthorized sudo usage
    issues.extend(_check_sudo_usage())
    
    # Check for unexpected open ports
    issues.extend(_check_open_ports())
    
    # Check for suspicious processes
    issues.extend(_check_suspicious_processes())
    
    # Check for modified system files
    issues.extend(_check_modified_system_files())
    
    # Check for SSH configuration
    issues.extend(_check_ssh_config())
    
    # Check for firewall status
    issues.extend(_check_firewall_status())
    
    # Update global issues list
    _security_issues = issues
    
    return issues

def get_security_issues():
    """Get the current list of security issues"""
    return _security_issues

def set_check_interval(seconds):
    """Set the security check interval in seconds"""
    global _check_interval
    _check_interval = max(300, seconds)  # Minimum 5 minutes
    logger.info(f"Security check interval set to {_check_interval} seconds")

def _monitor_loop():
    """Main monitoring loop"""
    while not _stop_event.is_set():
        try:
            # Run security checks
            issues = check_security()
            
            # Log any high severity issues
            high_severity_issues = [i for i in issues if i['severity'] == 'high']
            if high_severity_issues:
                logger.warning(f"Found {len(high_severity_issues)} high severity security issues")
                for issue in high_severity_issues:
                    logger.warning(f"Security issue: {issue['description']}")
            
            # Wait for next check interval or until stop event
            _stop_event.wait(_check_interval)
        except Exception as e:
            logger.error(f"Error in security monitoring: {e}", exc_info=True)
            _stop_event.wait(300)  # Wait 5 minutes before retrying

def _check_failed_logins():
    """Check for failed login attempts"""
    issues = []
    
    try:
        # Check auth.log for failed login attempts
        cmd = "grep 'Failed password' /var/log/auth.log | wc -l"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            count = int(result.stdout.strip())
            if count > 10:
                severity = 'high' if count > 50 else 'medium'
                issues.append({
                    'id': "failed_login_attempts",
                    'severity': severity,
                    'description': f"Detected {count} failed login attempts",
                    'component': 'authentication',
                    'data': {
                        'count': count
                    }
                })
    except Exception as e:
        logger.error(f"Error checking failed logins: {e}", exc_info=True)
    
    return issues

def _check_sudo_usage():
    """Check for unauthorized sudo usage"""
    issues = []
    
    try:
        # Check sudo log for unauthorized attempts
        cmd = "grep 'authentication failure' /var/log/auth.log | grep sudo | wc -l"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            count = int(result.stdout.strip())
            if count > 5:
                severity = 'high' if count > 20 else 'medium'
                issues.append({
                    'id': "unauthorized_sudo_usage",
                    'severity': severity,
                    'description': f"Detected {count} unauthorized sudo attempts",
                    'component': 'authentication',
                    'data': {
                        'count': count
                    }
                })
    except Exception as e:
        logger.error(f"Error checking sudo usage: {e}", exc_info=True)
    
    return issues

def _check_open_ports():
    """Check for unexpected open ports"""
    issues = []
    
    try:
        # Get list of listening ports
        cmd = "ss -tuln | grep LISTEN"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Define allowed ports (customize based on your environment)
            allowed_ports = {
                22,    # SSH
                80,    # HTTP
                443,   # HTTPS
                3306,  # MySQL
                5432,  # PostgreSQL
                8000,  # Django development server
                8080   # Alternative HTTP
            }
            
            # Parse output to find listening ports
            port_pattern = r':(\d+)\s'
            ports = re.findall(port_pattern, result.stdout)
            
            for port in ports:
                port_num = int(port)
                if port_num not in allowed_ports:
                    issues.append({
                        'id': f"unexpected_open_port_{port}",
                        'severity': 'medium',
                        'description': f"Unexpected open port: {port}",
                        'component': 'network',
                        'data': {
                            'port': port_num
                        }
                    })
    except Exception as e:
        logger.error(f"Error checking open ports: {e}", exc_info=True)
    
    return issues

def _check_suspicious_processes():
    """Check for suspicious processes"""
    issues = []
    
    try:
        # List of potentially suspicious process names
        suspicious_names = [
            'nc', 'netcat', 'ncat',  # Netcat
            'nmap',                  # Network scanning
            'hydra', 'medusa',       # Password cracking
            'wireshark', 'tcpdump',  # Network sniffing
            'metasploit',            # Penetration testing
            'backdoor', 'rootkit'    # Malware
        ]
        
        # Get list of running processes
        cmd = "ps -eo comm"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            processes = result.stdout.strip().split('\n')
            
            for suspicious in suspicious_names:
                for process in processes:
                    if suspicious.lower() in process.lower():
                        issues.append({
                            'id': f"suspicious_process_{suspicious}",
                            'severity': 'high',
                            'description': f"Suspicious process detected: {process}",
                            'component': 'process',
                            'data': {
                                'process_name': process
                            }
                        })
    except Exception as e:
        logger.error(f"Error checking suspicious processes: {e}", exc_info=True)
    
    return issues

def _check_modified_system_files():
    """Check for modified system files"""
    issues = []
    
    try:
        # Check for modified system binaries
        critical_files = [
            '/bin/bash',
            '/bin/sh',
            '/bin/ls',
            '/bin/login',
            '/bin/su',
            '/usr/bin/sudo',
            '/etc/passwd',
            '/etc/shadow',
            '/etc/ssh/sshd_config'
        ]
        
        for file_path in critical_files:
            if os.path.exists(file_path):
                # Check if file was modified in the last 24 hours
                mtime = os.path.getmtime(file_path)
                if time.time() - mtime < 86400:  # 24 hours in seconds
                    issues.append({
                        'id': f"modified_system_file_{os.path.basename(file_path)}",
                        'severity': 'high',
                        'description': f"Recently modified system file: {file_path}",
                        'component': 'filesystem',
                        'data': {
                            'file_path': file_path,
                            'modified_time': time.ctime(mtime)
                        }
                    })
    except Exception as e:
        logger.error(f"Error checking modified system files: {e}", exc_info=True)
    
    return issues

def _check_ssh_config():
    """Check SSH configuration for security issues"""
    issues = []
    
    try:
        ssh_config_path = '/etc/ssh/sshd_config'
        if os.path.exists(ssh_config_path):
            with open(ssh_config_path, 'r') as f:
                config = f.read()
            
            # Check for root login
            if 'PermitRootLogin yes' in config:
                issues.append({
                    'id': "ssh_root_login_enabled",
                    'severity': 'high',
                    'description': "SSH root login is enabled",
                    'component': 'ssh',
                    'data': {
                        'config_file': ssh_config_path
                    }
                })
            
            # Check for password authentication
            if 'PasswordAuthentication yes' in config:
                issues.append({
                    'id': "ssh_password_auth_enabled",
                    'severity': 'medium',
                    'description': "SSH password authentication is enabled",
                    'component': 'ssh',
                    'data': {
                        'config_file': ssh_config_path
                    }
                })
    except Exception as e:
        logger.error(f"Error checking SSH config: {e}", exc_info=True)
    
    return issues

def _check_firewall_status():
    """Check if firewall is enabled"""
    issues = []
    
    try:
        # Check if ufw is active
        cmd = "ufw status | grep -q 'Status: active'"
        result = subprocess.run(cmd, shell=True)
        
        if result.returncode != 0:
            # Try checking iptables
            cmd = "iptables -L | grep -q 'Chain INPUT'"
            result = subprocess.run(cmd, shell=True)
            
            if result.returncode != 0:
                issues.append({
                    'id': "firewall_disabled",
                    'severity': 'high',
                    'description': "Firewall appears to be disabled",
                    'component': 'network',
                    'data': {}
                })
    except Exception as e:
        logger.error(f"Error checking firewall status: {e}", exc_info=True)
    
    return issues