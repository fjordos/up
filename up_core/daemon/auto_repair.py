import os
import time
import threading
import logging
import subprocess
from pathlib import Path
from django.conf import settings
from up_core.daemon import health_monitor, security_monitor

logger = logging.getLogger(__name__)

# Global variables
_repair_thread = None
_stop_event = threading.Event()
_repair_interval = 3600  # 1 hour

def start():
    """Start the auto-repair thread"""
    global _repair_thread, _stop_event
    
    if _repair_thread and _repair_thread.is_alive():
        logger.info("Auto-repair already running")
        return
    
    _stop_event.clear()
    _repair_thread = threading.Thread(target=_repair_loop, daemon=True)
    _repair_thread.start()
    logger.info("Auto-repair started")

def stop():
    """Stop the auto-repair thread"""
    global _repair_thread, _stop_event
    
    if not _repair_thread or not _repair_thread.is_alive():
        logger.info("Auto-repair not running")
        return
    
    _stop_event.set()
    _repair_thread.join(timeout=5)
    logger.info("Auto-repair stopped")

def _repair_loop():
    """Main repair loop"""
    while not _stop_event.is_set():
        try:
            # Check for issues that can be auto-repaired
            health_issues = health_monitor.check_health()
            security_issues = security_monitor.check_security()
            
            # Attempt to repair critical issues automatically
            for issue in health_issues + security_issues:
                if issue['severity'] == 'high':
                    repair_issue(issue['id'])
            
            # Wait for next repair interval or until stop event
            _stop_event.wait(_repair_interval)
        except Exception as e:
            logger.error(f"Error in auto-repair: {e}", exc_info=True)
            _stop_event.wait(10)  # Wait a bit before retrying

def repair_issue(issue_id):
    """Repair a specific issue by ID"""
    logger.info(f"Attempting to repair issue: {issue_id}")
    
    try:
        # Disk usage issues
        if issue_id.startswith('disk_usage_'):
            return _repair_disk_usage(issue_id)
        
        # CPU usage issues
        elif issue_id == 'cpu_usage_high':
            return _repair_cpu_usage()
        
        # Memory usage issues
        elif issue_id == 'memory_usage_high':
            return _repair_memory_usage()
            
        # SSH brute force issues
        elif issue_id.startswith('ssh_brute_force_'):
            return _repair_ssh_brute_force(issue_id)
            
        # Unexpected open port issues
        elif issue_id.startswith('unexpected_open_port_'):
            return _repair_open_port(issue_id)
            
        # Security updates issues
        elif issue_id == 'security_updates_available':
            return _repair_security_updates()
            
        # Suspicious process issues
        elif issue_id.startswith('suspicious_process_'):
            return _repair_suspicious_process(issue_id)
            
        else:
            logger.warning(f"No repair method available for issue: {issue_id}")
            return {
                'success': False,
                'id': issue_id,
                'message': 'No repair method available for this issue'
            }
            
    except Exception as e:
        logger.error(f"Failed to repair issue {issue_id}: {e}", exc_info=True)
        return {
            'success': False,
            'id': issue_id,
            'message': f"Error during repair: {str(e)}"
        }

def repair_all():
    """Attempt to repair all detected issues"""
    results = []
    
    try:
        # Get all issues
        health_issues = health_monitor.check_health()
        security_issues = security_monitor.check_security()
        all_issues = health_issues + security_issues
        
        # Attempt to repair each issue
        for issue in all_issues:
            result = repair_issue(issue['id'])
            results.append(result)
            
    except Exception as e:
        logger.error(f"Error in repair_all: {e}", exc_info=True)
        
    return results

def _repair_disk_usage(issue_id):
    """Repair disk usage issues"""
    logger.info(f"Repairing disk usage issue: {issue_id}")
    
    try:
        # Extract mountpoint from issue_id
        mountpoint = issue_id.replace('disk_usage_', '').replace('_', '/')
        if not mountpoint.startswith('/'):
            mountpoint = '/' + mountpoint
            
        # Clean package cache if it's the root filesystem
        if mountpoint == '/':
            # Clean apt cache on Debian/Ubuntu
            if os.path.exists('/usr/bin/apt'):
                subprocess.run(['apt-get', 'clean'], check=True)
                subprocess.run(['apt-get', 'autoremove', '-y'], check=True)
                
            # Clean yum cache on RHEL/CentOS
            elif os.path.exists('/usr/bin/yum'):
                subprocess.run(['yum', 'clean', 'all'], check=True)
                
            # Remove old log files
            subprocess.run('find /var/log -type f -name "*.gz" -delete', shell=True, check=False)
            subprocess.run('find /var/log -type f -name "*.1" -delete', shell=True, check=False)
            
        # Remove temporary files
        temp_dirs = ['/tmp', '/var/tmp']
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                subprocess.run(f'find {temp_dir} -type f -atime +7 -delete', shell=True, check=False)
                
        return {
            'success': True,
            'id': issue_id,
            'message': f"Cleaned up disk space on {mountpoint}"
        }
    except Exception as e:
        logger.error(f"Failed to repair disk usage: {e}", exc_info=True)
        return {
            'success': False,
            'id': issue_id,
            'message': f"Failed to clean up disk space: {str(e)}"
        }

def _repair_cpu_usage():
    """Repair CPU usage issues"""
    logger.info("Repairing high CPU usage")
    
    try:
        # Find processes using high CPU
        cmd = "ps aux --sort=-%cpu | head -11"  # Get top 10 CPU-consuming processes
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        
        # Log the top CPU consumers
        logger.info(f"Top CPU consumers:\n{result.stdout}")
        
        # Look for runaway processes (using more than 90% CPU)
        high_cpu_pids = []
        for line in result.stdout.splitlines()[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 3:
                pid = parts[1]
                cpu_percent = float(parts[2])
                if cpu_percent > 90:
                    high_cpu_pids.append(pid)
        
        # Terminate runaway processes if found
        if high_cpu_pids:
            for pid in high_cpu_pids:
                try:
                    # Send SIGTERM first
                    subprocess.run(['kill', pid], check=False)
                    logger.info(f"Sent SIGTERM to process {pid}")
                except Exception as e:
                    logger.error(f"Failed to terminate process {pid}: {e}")
            
            return {
                'success': True,
                'id': 'cpu_usage_high',
                'message': f"Terminated {len(high_cpu_pids)} high CPU processes"
            }
        else:
            # No runaway processes found
            return {
                'success': False,
                'id': 'cpu_usage_high',
                'message': "No runaway processes found to terminate"
            }
    except Exception as e:
        logger.error(f"Failed to repair CPU usage: {e}", exc_info=True)
        return {
            'success': False,
            'id': 'cpu_usage_high',
            'message': f"Failed to repair CPU usage: {str(e)}"
        }

def _repair_memory_usage():
    """Repair memory usage issues"""
    logger.info("Repairing high memory usage")
    
    try:
        # Find processes using high memory
        cmd = "ps aux --sort=-%mem | head -11"  # Get top 10 memory-consuming processes
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        
        # Log the top memory consumers
        logger.info(f"Top memory consumers:\n{result.stdout}")
        
        # Clear system caches
        subprocess.run("sync && echo 3 > /proc/sys/vm/drop_caches", shell=True, check=False)
        logger.info("Cleared system caches")
        
        # Look for memory leaks (processes using more than 80% memory)
        high_mem_pids = []
        for line in result.stdout.splitlines()[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 4:
                pid = parts[1]
                mem_percent = float(parts[3])
                if mem_percent > 80:
                    high_mem_pids.append(pid)
        
        # Terminate memory-hogging processes if found
        if high_mem_pids:
            for pid in high_mem_pids:
                try:
                    # Send SIGTERM first
                    subprocess.run(['kill', pid], check=False)
                    logger.info(f"Sent SIGTERM to process {pid}")
                except Exception as e:
                    logger.error(f"Failed to terminate process {pid}: {e}")
            
            return {
                'success': True,
                'id': 'memory_usage_high',
                'message': f"Terminated {len(high_mem_pids)} high memory processes and cleared caches"
            }
        else:
            # No memory-hogging processes found, but caches were cleared
            return {
                'success': True,
                'id': 'memory_usage_high',
                'message': "Cleared system caches"
            }
    except Exception as e:
        logger.error(f"Failed to repair memory usage: {e}", exc_info=True)
        return {
            'success': False,
            'id': 'memory_usage_high',
            'message': f"Failed to repair memory usage: {str(e)}"
        }

def _repair_ssh_brute_force(issue_id):
    """Block IP addresses attempting SSH brute force"""
    logger.info(f"Repairing SSH brute force issue: {issue_id}")
    
    try:
        # Extract IP from issue_id
        ip = issue_id.replace('ssh_brute_force_', '').replace('_', '.')
        
        # Check if IP is valid
        import socket
        try:
            socket.inet_aton(ip)
        except socket.error:
            return {
                'success': False,
                'id': issue_id,
                'message': f"Invalid IP address: {ip}"
            }
        
        # Block the IP using iptables
        cmd = f"iptables -A INPUT -s {ip} -j DROP"
        subprocess.run(cmd, shell=True, check=True)
        logger.info(f"Blocked IP {ip} using iptables")
        
        # Make iptables rules persistent (depends on the distribution)
        if os.path.exists('/usr/bin/iptables-save'):
            if os.path.exists('/etc/iptables/rules.v4'):
                subprocess.run("iptables-save > /etc/iptables/rules.v4", shell=True, check=False)
            else:
                subprocess.run("iptables-save > /etc/iptables.rules", shell=True, check=False)
        
        return {
            'success': True,
            'id': issue_id,
            'message': f"Blocked IP {ip} using iptables"
        }
    except Exception as e:
        logger.error(f"Failed to block SSH brute force IP: {e}", exc_info=True)
        return {
            'success': False,
            'id': issue_id,
            'message': f"Failed to block IP: {str(e)}"
        }

def _repair_open_port(issue_id):
    """Close unexpected open ports"""
    logger.info(f"Repairing open port issue: {issue_id}")
    
    try:
        # Extract port from issue_id
        port = issue_id.replace('unexpected_open_port_', '')
        
        # Find process using the port
        cmd = f"lsof -i :{port} | grep LISTEN"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout:
            # Extract PID
            lines = result.stdout.strip().split('\n')
            if lines:
                parts = lines[0].split()
                if len(parts) > 1:
                    process_name = parts[0]
                    pid = parts[1]
                    
                    logger.info(f"Found process {process_name} (PID {pid}) using port {port}")
                    
                    # Terminate the process
                    subprocess.run(['kill', pid], check=False)
                    logger.info(f"Terminated process {pid}")
                    
                    return {
                        'success': True,
                        'id': issue_id,
                        'message': f"Closed port {port} by terminating process {process_name} (PID {pid})"
                    }
        
        # If we couldn't find or kill the process, return failure
        return {
            'success': False,
            'id': issue_id,
            'message': f"Could not close port {port}: no process found or failed to terminate"
        }
    except Exception as e:
        logger.error(f"Failed to close open port: {e}", exc_info=True)
        return {
            'success': False,
            'id': issue_id,
            'message': f"Failed to close port: {str(e)}"
        }

def _repair_security_updates():
    """Apply available security updates"""
    logger.info("Repairing security updates")
    
    try:
        # Update package lists
        if os.path.exists('/usr/bin/apt'):
            subprocess.run(['apt-get', 'update'], check=True)
            # Upgrade security updates
            subprocess.run(['apt-get', 'upgrade', '--only-upgrade', '-y', '-o', 'APT::Get::Show-Upgraded=true'], check=True)
        elif os.path.exists('/usr/bin/yum'):
            subprocess.run(['yum', 'update', '-y', '--security'], check=True)
        elif os.path.exists('/usr/bin/dnf'):
            subprocess.run(['dnf', 'upgrade', '-y', '--security'], check=True)
        elif os.path.exists('/usr/bin/pacman'):
            subprocess.run(['pacman', '-Syuq', '--needed'], check=True)
        else:
            return {
                'success': False,
                'id': 'security_updates_available',
                'message': "No supported package manager found"
            }
        
        return {
            'success': True,
            'id': 'security_updates_available',
            'message': "Applied available security updates"
        }
    except Exception as e:
        logger.error(f"Failed to apply security updates: {e}", exc_info=True)
        return {
            'success': False,
            'id': 'security_updates_available',
            'message': f"Failed to apply security updates: {str(e)}"
        }

def _repair_suspicious_process(issue_id):
    """Terminate suspicious processes"""
    logger.info(f"Repairing suspicious process issue: {issue_id}")
    
    try:
        # Extract process name from issue_id
        process_name = issue_id.replace('suspicious_process_', '')
        
        # Find and terminate the process
        cmd = f"pgrep {process_name}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout:
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                try:
                    subprocess.run(['kill', pid], check=False)
                    logger.info(f"Terminated suspicious process {process_name} (PID {pid})")
                except Exception as e:
                    logger.error(f"Failed to terminate process {pid}: {e}")
            
            return {
                'success': True,
                'id': issue_id,
                'message': f"Terminated suspicious process {process_name}"
            }
        else:
            return {
                'success': False,
                'id': issue_id,
                'message': f"No suspicious process {process_name} found"
            }
    except Exception as e:
        logger.error(f"Failed to repair suspicious process: {e}", exc_info=True)
        return {
            'success': False,
            'id': issue_id,
            'message': f"Failed to repair suspicious process: {str(e)}"
        }