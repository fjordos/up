import os
import time
import psutil
import logging
import threading
import subprocess
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

# Global variables
_monitor_thread = None
_stop_event = threading.Event()
_check_interval = 300  # 5 minutes by default
_health_issues = []

# Thresholds for health checks
DISK_USAGE_THRESHOLD = 90  # Percentage
MEMORY_USAGE_THRESHOLD = 90  # Percentage
CPU_USAGE_THRESHOLD = 90  # Percentage
LOAD_THRESHOLD_FACTOR = 1.5  # Multiple of CPU count
INODE_USAGE_THRESHOLD = 90  # Percentage
SWAP_USAGE_THRESHOLD = 80  # Percentage

def start():
    """Start the health monitoring thread"""
    global _monitor_thread, _stop_event
    
    if _monitor_thread and _monitor_thread.is_alive():
        logger.info("Health monitoring already running")
        return
    
    _stop_event.clear()
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _monitor_thread.start()
    logger.info("Health monitoring started")

def stop():
    """Stop the health monitoring thread"""
    global _monitor_thread, _stop_event
    
    if _monitor_thread and _monitor_thread.is_alive():
        logger.info("Stopping health monitoring")
        _stop_event.set()
        _monitor_thread.join(timeout=5)
        if _monitor_thread.is_alive():
            logger.warning("Health monitoring thread did not stop gracefully")
        else:
            logger.info("Health monitoring stopped")
    else:
        logger.info("Health monitoring not running")

def check_health():
    """Run all health checks and return issues"""
    global _health_issues
    
    issues = []
    
    # Check disk usage
    issues.extend(_check_disk_usage())
    
    # Check memory usage
    issues.extend(_check_memory_usage())
    
    # Check CPU load
    issues.extend(_check_cpu_load())
    
    # Check for zombie processes
    issues.extend(_check_zombie_processes())
    
    # Check for inode usage
    issues.extend(_check_inode_usage())
    
    # Check for swap usage
    issues.extend(_check_swap_usage())
    
    # Check for system updates
    issues.extend(_check_system_updates())
    
    # Update global issues list
    _health_issues = issues
    
    return issues

def check_performance():
    """Run performance-specific checks"""
    issues = []
    
    # Check for high I/O wait
    issues.extend(_check_io_wait())
    
    # Check for network saturation
    issues.extend(_check_network_saturation())
    
    # Check for slow disk I/O
    issues.extend(_check_disk_io_performance())
    
    return issues

def get_health_issues():
    """Get the current list of health issues"""
    return _health_issues

def set_check_interval(seconds):
    """Set the health check interval in seconds"""
    global _check_interval
    _check_interval = max(60, seconds)  # Minimum 1 minute
    logger.info(f"Health check interval set to {_check_interval} seconds")

def _monitor_loop():
    """Main monitoring loop"""
    while not _stop_event.is_set():
        try:
            # Run health checks
            issues = check_health()
            
            # Log any high severity issues
            high_severity_issues = [i for i in issues if i['severity'] == 'high']
            if high_severity_issues:
                logger.warning(f"Found {len(high_severity_issues)} high severity health issues")
                for issue in high_severity_issues:
                    logger.warning(f"Health issue: {issue['description']}")
            
            # Wait for next check interval or until stop event
            _stop_event.wait(_check_interval)
        except Exception as e:
            logger.error(f"Error in health monitoring: {e}", exc_info=True)
            _stop_event.wait(60)  # Wait a bit before retrying

def _check_disk_usage():
    """Check disk usage on all mounted filesystems"""
    issues = []
    
    try:
        partitions = psutil.disk_partitions(all=False)
        for partition in partitions:
            if partition.fstype and not any(x in partition.mountpoint for x in ['/boot', '/dev', '/proc', '/sys']):
                usage = psutil.disk_usage(partition.mountpoint)
                if usage.percent >= DISK_USAGE_THRESHOLD:
                    severity = 'high' if usage.percent >= 95 else 'medium'
                    issues.append({
                        'id': f"disk_usage_{partition.mountpoint.replace('/', '_')}",
                        'severity': severity,
                        'description': f"Disk usage at {usage.percent}% on {partition.mountpoint}",
                        'component': 'disk',
                        'data': {
                            'mountpoint': partition.mountpoint,
                            'usage_percent': usage.percent,
                            'total_gb': round(usage.total / (1024**3), 2),
                            'free_gb': round(usage.free / (1024**3), 2)
                        }
                    })
    except Exception as e:
        logger.error(f"Error checking disk usage: {e}", exc_info=True)
    
    return issues

def _check_memory_usage():
    """Check system memory usage"""
    issues = []
    
    try:
        memory = psutil.virtual_memory()
        if memory.percent >= MEMORY_USAGE_THRESHOLD:
            severity = 'high' if memory.percent >= 95 else 'medium'
            issues.append({
                'id': "high_memory_usage",
                'severity': severity,
                'description': f"Memory usage at {memory.percent}%",
                'component': 'memory',
                'data': {
                    'usage_percent': memory.percent,
                    'total_gb': round(memory.total / (1024**3), 2),
                    'available_gb': round(memory.available / (1024**3), 2)
                }
            })
    except Exception as e:
        logger.error(f"Error checking memory usage: {e}", exc_info=True)
    
    return issues

def _check_cpu_load():
    """Check CPU load average"""
    issues = []
    
    try:
        # Get number of CPU cores
        cpu_count = psutil.cpu_count()
        
        # Get load averages (1, 5, 15 minutes)
        load1, load5, load15 = os.getloadavg()
        
        # Check if load average exceeds threshold
        threshold = cpu_count * LOAD_THRESHOLD_FACTOR
        
        if load1 > threshold:
            severity = 'high' if load1 > threshold * 1.5 else 'medium'
            issues.append({
                'id': "high_cpu_load",
                'severity': severity,
                'description': f"High CPU load: {load1:.2f} (threshold: {threshold:.2f})",
                'component': 'cpu',
                'data': {
                    'load1': load1,
                    'load5': load5,
                    'load15': load15,
                    'cpu_count': cpu_count,
                    'threshold': threshold
                }
            })
        
        # Also check current CPU usage percentage
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent >= CPU_USAGE_THRESHOLD:
            severity = 'high' if cpu_percent >= 95 else 'medium'
            issues.append({
                'id': "high_cpu_usage",
                'severity': severity,
                'description': f"CPU usage at {cpu_percent}%",
                'component': 'cpu',
                'data': {
                    'usage_percent': cpu_percent
                }
            })
    except Exception as e:
        logger.error(f"Error checking CPU load: {e}", exc_info=True)
    
    return issues

def _check_zombie_processes():
    """Check for zombie processes"""
    issues = []
    
    try:
        zombies = []
        for proc in psutil.process_iter(['pid', 'name', 'status']):
            try:
                if proc.info['status'] == psutil.STATUS_ZOMBIE:
                    zombies.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if zombies:
            severity = 'medium' if len(zombies) > 10 else 'low'
            issues.append({
                'id': "zombie_processes",
                'severity': severity,
                'description': f"Found {len(zombies)} zombie processes",
                'component': 'process',
                'data': {
                    'count': len(zombies),
                    'zombies': zombies[:10]  # Limit to first 10
                }
            })
    except Exception as e:
        logger.error(f"Error checking zombie processes: {e}", exc_info=True)
    
    return issues

def _check_inode_usage():
    """Check inode usage on all mounted filesystems"""
    issues = []
    
    try:
        # Use df command to get inode usage
        result = subprocess.run(
            ["df", "-i"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 5:
                    filesystem = parts[0]
                    inodes_used_percent = parts[4].rstrip('%')
                    mountpoint = parts[5] if len(parts) >= 6 else parts[4]
                    
                    # Skip special filesystems
                    if any(x in mountpoint for x in ['/boot', '/dev', '/proc', '/sys']):
                        continue
                    
                    try:
                        inode_percent = int(inodes_used_percent)
                        if inode_percent >= INODE_USAGE_THRESHOLD:
                            severity = 'high' if inode_percent >= 95 else 'medium'
                            issues.append({
                                'id': f"inode_usage_{mountpoint.replace('/', '_')}",
                                'severity': severity,
                                'description': f"Inode usage at {inode_percent}% on {mountpoint}",
                                'component': 'disk',
                                'data': {
                                    'mountpoint': mountpoint,
                                    'usage_percent': inode_percent,
                                    'filesystem': filesystem
                                }
                            })
                    except ValueError:
                        pass
    except Exception as e:
        logger.error(f"Error checking inode usage: {e}", exc_info=True)
    
    return issues

def _check_swap_usage():
    """Check swap space usage"""
    issues = []
    
    try:
        swap = psutil.swap_memory()
        if swap.total > 0 and swap.percent >= SWAP_USAGE_THRESHOLD:
            severity = 'high' if swap.percent >= 95 else 'medium'
            issues.append({
                'id': "high_swap_usage",
                'severity': severity,
                'description': f"Swap usage at {swap.percent}%",
                'component': 'memory',
                'data': {
                    'usage_percent': swap.percent,
                    'total_gb': round(swap.total / (1024**3), 2),
                    'used_gb': round(swap.used / (1024**3), 2)
                }
            })
    except Exception as e:
        logger.error(f"Error checking swap usage: {e}", exc_info=True)
    
    return issues

def _check_system_updates():
    """Check for available system updates"""
    issues = []
    
    try:
        # Example for Debian-based systems using apt
        result = subprocess.run(
            ["apt", "list", "--upgradable"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 and "Listing..." not in result.stdout:
            updates = result.stdout.strip().split('\n')
            if updates:
                severity = 'low'
                issues.append({
                    'id': "system_updates_available",
                    'severity': severity,
                    'description': f"{len(updates)} system updates available",
                    'component': 'system',
                    'data': {
                        'count': len(updates),
                        'updates': updates[:10]  # Limit to first 10
                    }
                })
    except Exception as e:
        logger.error(f"Error checking system updates: {e}", exc_info=True)
    
    return issues

def _check_io_wait():
    """Check for high I/O wait times"""
    issues = []
    
    try:
        # Placeholder for actual I/O wait check logic
        # This is a simplified example and may need platform-specific implementation
        io_wait = psutil.cpu_times_percent(interval=1).iowait
        if io_wait > 20:  # Example threshold
            severity = 'high' if io_wait > 30 else 'medium'
            issues.append({
                'id': "high_io_wait",
                'severity': severity,
                'description': f"High I/O wait time: {io_wait}%",
                'component': 'io',
                'data': {
                    'io_wait_percent': io_wait
                }
            })
    except Exception as e:
        logger.error(f"Error checking I/O wait: {e}", exc_info=True)
    
    return issues

def _check_network_saturation():
    """Check for network saturation"""
    issues = []
    
    try:
        # Placeholder for actual network saturation check logic
        # This is a simplified example and may need platform-specific implementation
        net_io = psutil.net_io_counters()
        bytes_sent = net_io.bytes_sent
        bytes_recv = net_io.bytes_recv
        
        # Example threshold (1 GB/s)
        threshold = 1024**3
        if bytes_sent > threshold or bytes_recv > threshold:
            severity = 'high'
            issues.append({
                'id': "network_saturation",
                'severity': severity,
                'description': f"Network saturation detected",
                'component': 'network',
                'data': {
                    'bytes_sent': bytes_sent,
                    'bytes_recv': bytes_recv,
                    'threshold': threshold
                }
            })
    except Exception as e:
        logger.error(f"Error checking network saturation: {e}", exc_info=True)
    
    return issues

def _check_disk_io_performance():
    """Check for slow disk I/O performance"""
    issues = []
    
    try:
        # Placeholder for actual disk I/O performance check logic
        # This is a simplified example and may need platform-specific implementation
        disk_io = psutil.disk_io_counters()
        read_time = disk_io.read_time
        write_time = disk_io.write_time
        
        # Example threshold (1000 ms)
        threshold = 1000
        if read_time > threshold or write_time > threshold:
            severity = 'high'
            issues.append({
                'id': "slow_disk_io",
                'severity': severity,
                'description': f"Slow disk I/O performance detected",
                'component': 'disk',
                'data': {
                    'read_time_ms': read_time,
                    'write_time_ms': write_time,
                    'threshold': threshold
                }
            })
    except Exception as e:
        logger.error(f"Error checking disk I/O performance: {e}", exc_info=True)
    
    return issues