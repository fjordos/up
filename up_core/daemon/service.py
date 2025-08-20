import os
import sys
import time
import signal
import logging
import subprocess
import psutil
from pathlib import Path
from django.conf import settings
from up_core.daemon import health_monitor, security_monitor, auto_repair

logger = logging.getLogger(__name__)

# Constants
DAEMON_PID_FILE = Path('/var/run/up-daemon.pid')
DAEMON_LOG_FILE = Path('/var/log/up-daemon.log')

# Ensure log directory exists
if not DAEMON_LOG_FILE.parent.exists():
    try:
        DAEMON_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        logger.error("Permission denied when creating log directory. Try running with sudo.")
        sys.exit(1)

# Ensure pid directory exists
if not DAEMON_PID_FILE.parent.exists():
    try:
        DAEMON_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        logger.error("Permission denied when creating PID directory. Try running with sudo.")
        sys.exit(1)

def start_daemon():
    """Start the daemon process"""
    if is_daemon_running():
        logger.info("Daemon is already running")
        return True
    
    try:
        # Fork the process
        pid = os.fork()
        if pid > 0:
            # Exit the parent process
            return True
    except OSError as e:
        logger.error(f"Fork failed: {e}")
        return False
    
    # Decouple from parent environment
    os.chdir('/')
    os.setsid()
    os.umask(0)
    
    # Fork again
    try:
        pid = os.fork()
        if pid > 0:
            # Exit from second parent
            sys.exit(0)
    except OSError as e:
        logger.error(f"Second fork failed: {e}")
        sys.exit(1)
    
    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    
    with open('/dev/null', 'r') as si, \
         open(str(DAEMON_LOG_FILE), 'a+') as so, \
         open(str(DAEMON_LOG_FILE), 'a+') as se:
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())
    
    # Write PID file
    with open(str(DAEMON_PID_FILE), 'w') as f:
        f.write(str(os.getpid()))
    
    # Set up signal handlers
    signal.signal(signal.SIGTERM, _handle_sigterm)
    
    # Start monitoring and auto-repair
    logger.info("Starting UP daemon")
    health_monitor.start()
    security_monitor.start()
    auto_repair.start()
    
    # Main loop
    while True:
        time.sleep(60)
        
        # Check if we should exit
        if not os.path.exists(str(DAEMON_PID_FILE)):
            logger.info("PID file removed, shutting down")
            _cleanup()
            sys.exit(0)

def stop_daemon():
    """Stop the daemon process"""
    if not is_daemon_running():
        logger.info("Daemon is not running")
        return True
    
    try:
        with open(str(DAEMON_PID_FILE), 'r') as f:
            pid = int(f.read().strip())
        
        # Send SIGTERM to the process
        os.kill(pid, signal.SIGTERM)
        
        # Wait for process to terminate
        for _ in range(10):  # Wait up to 10 seconds
            if not is_daemon_running():
                return True
            time.sleep(1)
        
        # If still running, force kill
        if is_daemon_running():
            os.kill(pid, signal.SIGKILL)
            logger.warning("Daemon did not terminate gracefully, sent SIGKILL")
            
            # Remove PID file if it still exists
            if os.path.exists(str(DAEMON_PID_FILE)):
                os.unlink(str(DAEMON_PID_FILE))
        
        return True
    except Exception as e:
        logger.error(f"Error stopping daemon: {e}")
        return False

def is_daemon_running():
    """Check if the daemon is running"""
    if not os.path.exists(str(DAEMON_PID_FILE)):
        return False
    
    try:
        with open(str(DAEMON_PID_FILE), 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process exists
        os.kill(pid, 0)
        
        # Check if it's our daemon process
        try:
            process = psutil.Process(pid)
            cmdline = process.cmdline()
            return any('python' in cmd for cmd in cmdline) and any('up' in cmd for cmd in cmdline)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    except (OSError, ValueError):
        # Process doesn't exist or PID file is invalid
        if os.path.exists(str(DAEMON_PID_FILE)):
            os.unlink(str(DAEMON_PID_FILE))
        return False

def daemon_status():
    """Get the status of the daemon"""
    status = {
        'running': is_daemon_running(),
        'pid_file': str(DAEMON_PID_FILE),
        'log_file': str(DAEMON_LOG_FILE),
    }
    
    if status['running']:
        try:
            with open(str(DAEMON_PID_FILE), 'r') as f:
                pid = int(f.read().strip())
            
            process = psutil.Process(pid)
            status['pid'] = pid
            status['uptime'] = time.time() - process.create_time()
            status['memory_usage'] = process.memory_info().rss
            status['cpu_percent'] = process.cpu_percent(interval=0.1)
            
            # Get health and security issues
            if hasattr(health_monitor, 'get_health_issues'):
                status['health_issues'] = len(health_monitor.get_health_issues())
            
            if hasattr(security_monitor, 'get_security_issues'):
                status['security_issues'] = len(security_monitor.get_security_issues())
        except Exception as e:
            logger.error(f"Error getting daemon status: {e}")
    
    return status

def get_logs(lines=100):
    """Get the last N lines from the daemon log"""
    if not DAEMON_LOG_FILE.exists():
        return ["No log file found"]
    
    try:
        cmd = f"tail -n {lines} {DAEMON_LOG_FILE}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split('\n')
        else:
            return [f"Error getting logs: {result.stderr}"]
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        return [f"Error getting logs: {e}"]

def follow_logs():
    """Generator that yields new log lines as they are written"""
    if not DAEMON_LOG_FILE.exists():
        yield "No log file found"
        return
    
    try:
        # Use tail -f to follow the log file
        process = subprocess.Popen(
            ["tail", "-f", "-n", "0", str(DAEMON_LOG_FILE)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        while True:
            line = process.stdout.readline()
            if not line:
                break
            yield line.rstrip()
    except Exception as e:
        logger.error(f"Error following logs: {e}")
        yield f"Error following logs: {e}"
    finally:
        if 'process' in locals():
            process.terminate()

def _handle_sigterm(signum, frame):
    """Handle SIGTERM signal"""
    logger.info("Received SIGTERM signal, shutting down")
    _cleanup()
    sys.exit(0)

def _cleanup():
    """Clean up resources before exiting"""
    try:
        # Stop all monitoring threads
        health_monitor.stop()
        security_monitor.stop()
        auto_repair.stop()
        
        # Remove PID file
        if os.path.exists(str(DAEMON_PID_FILE)):
            os.unlink(str(DAEMON_PID_FILE))
            
        logger.info("Daemon shutdown complete")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
