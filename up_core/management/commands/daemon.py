import time
import logging
from django.core.management.base import BaseCommand, CommandError
from up_core.daemon import service

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Manage the UP daemon process'

    def add_arguments(self, parser):
        parser.add_argument('action', type=str, choices=['start', 'stop', 'restart', 'status', 'logs', 'follow'])
        parser.add_argument('--lines', type=int, default=100, help='Number of log lines to show')

    def handle(self, *args, **options):
        action = options['action']
        
        if action == 'start':
            self.stdout.write("Starting UP daemon...")
            if service.start_daemon():
                self.stdout.write(self.style.SUCCESS("Daemon started successfully"))
            else:
                self.stdout.write(self.style.ERROR("Failed to start daemon"))
                
        elif action == 'stop':
            self.stdout.write("Stopping UP daemon...")
            if service.stop_daemon():
                self.stdout.write(self.style.SUCCESS("Daemon stopped successfully"))
            else:
                self.stdout.write(self.style.ERROR("Failed to stop daemon"))
                
        elif action == 'restart':
            self.stdout.write("Restarting UP daemon...")
            service.stop_daemon()
            time.sleep(2)  # Give it time to stop
            if service.start_daemon():
                self.stdout.write(self.style.SUCCESS("Daemon restarted successfully"))
            else:
                self.stdout.write(self.style.ERROR("Failed to restart daemon"))
                
        elif action == 'status':
            status = service.daemon_status()
            if status['running']:
                self.stdout.write(self.style.SUCCESS("Daemon is running"))
                self.stdout.write(f"PID: {status.get('pid', 'Unknown')}")
                
                if 'uptime' in status:
                    uptime_seconds = status['uptime']
                    days, remainder = divmod(uptime_seconds, 86400)
                    hours, remainder = divmod(remainder, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
                    self.stdout.write(f"Uptime: {uptime_str}")
                
                if 'memory_usage' in status:
                    memory_mb = status['memory_usage'] / (1024 * 1024)
                    self.stdout.write(f"Memory usage: {memory_mb:.2f} MB")
                
                if 'cpu_percent' in status:
                    self.stdout.write(f"CPU usage: {status['cpu_percent']:.1f}%")
                
                if 'health_issues' in status:
                    self.stdout.write(f"Health issues: {status['health_issues']}")
                
                if 'security_issues' in status:
                    self.stdout.write(f"Security issues: {status['security_issues']}")
                
                self.stdout.write(f"Log file: {status['log_file']}")
                self.stdout.write(f"PID file: {status['pid_file']}")
            else:
                self.stdout.write(self.style.WARNING("Daemon is not running"))
                
        elif action == 'logs':
            lines = options['lines']
            self.stdout.write(f"Last {lines} lines from daemon log:")
            log_lines = service.get_logs(lines)
            for line in log_lines:
                self.stdout.write(line)
                
        elif action == 'follow':
            self.stdout.write("Following daemon log (Ctrl+C to stop):")
            try:
                for line in service.follow_logs():
                    self.stdout.write(line)
            except KeyboardInterrupt:
                self.stdout.write("\nStopped following logs")