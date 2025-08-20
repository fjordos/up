from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import argparse
import sys
import logging
from up_core.admin import (
    nginx_manager, 
    vm_manager, 
    container_manager, 
    storage_manager, 
    user_manager, 
    backup_manager,
    network_manager,
    security_manager
)
from up_core.user import (
    website_manager,
    database_manager,
    mail_manager,
    dns_manager,
    sftp_manager,
    resource_manager
)
from up_core.daemon import (
    health_monitor,
    security_monitor,
    auto_repair
)

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'UP - Secure Hosting Environment Management Tool'

    def add_arguments(self, parser):
        # Main subparsers
        subparsers = parser.add_subparsers(dest='command', help='Command')
        
        # Admin commands
        admin_parser = subparsers.add_parser('admin', help='Admin operations')
        admin_subparsers = admin_parser.add_subparsers(dest='admin_command', help='Admin command')
        
        # Nginx management
        nginx_parser = admin_subparsers.add_parser('nginx', help='Nginx reverse proxy management')
        nginx_subparsers = nginx_parser.add_subparsers(dest='nginx_command', help='Nginx command')
        
        nginx_add = nginx_subparsers.add_parser('add', help='Add a new Nginx reverse proxy')
        nginx_add.add_argument('--ip', required=True, help='IP address or range')
        nginx_add.add_argument('--domain', required=True, help='Wildcard domain')
        
        nginx_remove = nginx_subparsers.add_parser('remove', help='Remove an Nginx reverse proxy')
        nginx_remove.add_argument('--ip', required=True, help='IP address or range')
        
        nginx_list = nginx_subparsers.add_parser('list', help='List all Nginx reverse proxies')
        
        # VM management
        vm_parser = admin_subparsers.add_parser('vm', help='Virtual machine management')
        vm_subparsers = vm_parser.add_subparsers(dest='vm_command', help='VM command')
        
        vm_create = vm_subparsers.add_parser('create', help='Create a new VM')
        vm_create.add_argument('--name', required=True, help='VM name')
        vm_create.add_argument('--hypervisor', required=True, help='Hypervisor name')
        vm_create.add_argument('--memory', type=int, default=2048, help='Memory in MB')
        vm_create.add_argument('--vcpus', type=int, default=2, help='Number of vCPUs')
        vm_create.add_argument('--disk', type=int, default=20, help='Disk size in GB')
        vm_create.add_argument('--image', required=True, help='OS image')
        
        vm_delete = vm_subparsers.add_parser('delete', help='Delete a VM')
        vm_delete.add_argument('--name', required=True, help='VM name')
        
        vm_list = vm_subparsers.add_parser('list', help='List all VMs')
        vm_list.add_argument('--hypervisor', help='Filter by hypervisor')
        
        vm_start = vm_subparsers.add_parser('start', help='Start a VM')
        vm_start.add_argument('--name', required=True, help='VM name')
        
        vm_stop = vm_subparsers.add_parser('stop', help='Stop a VM')
        vm_stop.add_argument('--name', required=True, help='VM name')
        
        vm_resize = vm_subparsers.add_parser('resize', help='Resize a VM')
        vm_resize.add_argument('--name', required=True, help='VM name')
        vm_resize.add_argument('--memory', type=int, help='New memory in MB')
        vm_resize.add_argument('--vcpus', type=int, help='New number of vCPUs')
        vm_resize.add_argument('--disk', type=int, help='New disk size in GB')
        
        # Container management
        container_parser = admin_subparsers.add_parser('container', help='Container management')
        container_subparsers = container_parser.add_subparsers(dest='container_command', help='Container command')
        
        container_create = container_subparsers.add_parser('create', help='Create a new container')
        container_create.add_argument('--name', required=True, help='Container name')
        container_create.add_argument('--host', required=True, help='Host VM or server')
        container_create.add_argument('--image', required=True, help='Container image')
        container_create.add_argument('--user', required=True, help='User owner')
        container_create.add_argument('--memory', type=int, help='Memory limit in MB')
        container_create.add_argument('--cpu', type=float, help='CPU limit')
        
        container_delete = container_subparsers.add_parser('delete', help='Delete a container')
        container_delete.add_argument('--name', required=True, help='Container name')
        container_delete.add_argument('--host', required=True, help='Host VM or server')
        
        container_list = container_subparsers.add_parser('list', help='List all containers')
        container_list.add_argument('--host', help='Filter by host')
        container_list.add_argument('--user', help='Filter by user')
        
        # Storage management
        storage_parser = admin_subparsers.add_parser('storage', help='Storage management')
        storage_subparsers = storage_parser.add_subparsers(dest='storage_command', help='Storage command')
        
        storage_create = storage_subparsers.add_parser('create', help='Create a new storage')
        storage_create.add_argument('--name', required=True, help='Storage name')
        storage_create.add_argument('--type', required=True, choices=['block', 'file'], help='Storage type')
        storage_create.add_argument('--size', type=int, required=True, help='Size in GB')
        storage_create.add_argument('--host', required=True, help='Host VM or server')
        
        storage_attach = storage_subparsers.add_parser('attach', help='Attach storage to VM or container')
        storage_attach.add_argument('--storage', required=True, help='Storage name')
        storage_attach.add_argument('--target', required=True, help='Target VM or container')
        storage_attach.add_argument('--mount', required=True, help='Mount point')
        
        storage_detach = storage_subparsers.add_parser('detach', help='Detach storage from VM or container')
        storage_detach.add_argument('--storage', required=True, help='Storage name')
        storage_detach.add_argument('--target', required=True, help='Target VM or container')
        
        storage_list = storage_subparsers.add_parser('list', help='List all storages')
        
        # User management
        user_parser = admin_subparsers.add_parser('user', help='User management')
        user_subparsers = user_parser.add_subparsers(dest='user_command', help='User command')
        
        user_create = user_subparsers.add_parser('create', help='Create a new user')
        user_create.add_argument('--username', required=True, help='Username')
        user_create.add_argument('--email', required=True, help='Email')
        user_create.add_argument('--password', required=True, help='Password')
        user_create.add_argument('--admin', action='store_true', help='Admin privileges')
        
        user_delete = user_subparsers.add_parser('delete', help='Delete a user')
        user_delete.add_argument('--username', required=True, help='Username')
        
        user_list = user_subparsers.add_parser('list', help='List all users')
        
        user_update = user_subparsers.add_parser('update', help='Update user details')
        user_update.add_argument('--username', required=True, help='Username')
        user_update.add_argument('--email', help='New email')
        user_update.add_argument('--password', help='New password')
        user_update.add_argument('--admin', action='store_true', help='Grant admin privileges')
        user_update.add_argument('--no-admin', action='store_true', help='Revoke admin privileges')
        
        # Backup management
        backup_parser = admin_subparsers.add_parser('backup', help='Backup management')
        backup_subparsers = backup_parser.add_subparsers(dest='backup_command', help='Backup command')
        
        backup_create = backup_subparsers.add_parser('create', help='Create a backup')
        backup_create.add_argument('--type', required=True, choices=['full', 'incremental'], help='Backup type')
        backup_create.add_argument('--target', help='Target VM, container, or user')
        
        backup_restore = backup_subparsers.add_parser('restore', help='Restore from backup')
        backup_restore.add_argument('--id', required=True, help='Backup ID')
        backup_restore.add_argument('--target', help='Restore target')
        
        backup_list = backup_subparsers.add_parser('list', help='List backups')
        backup_list.add_argument('--target', help='Filter by target')
        
        # Mount management
        mount_parser = admin_subparsers.add_parser('mount', help='Mount management')
        mount_subparsers = mount_parser.add_subparsers(dest='mount_command', help='Mount command')
        
        mount_add = mount_subparsers.add_parser('add', help='Add a new mount')
        mount_add.add_argument('--source', required=True, help='Source path or URL')
        mount_add.add_argument('--target', required=True, help='Target VM or container')
        mount_add.add_argument('--mount-point', required=True, help='Mount point')
        mount_add.add_argument('--type', required=True, choices=['nfs', 'smb', 'block'], help='Mount type')
        mount_add.add_argument('--permanent', action='store_true', help='Permanent mount')
        
        mount_remove = mount_subparsers.add_parser('remove', help='Remove a mount')
        mount_remove.add_argument('--target', required=True, help='Target VM or container')
        mount_remove.add_argument('--mount-point', required=True, help='Mount point')
        
        mount_list = mount_subparsers.add_parser('list', help='List all mounts')
        mount_list.add_argument('--target', help='Filter by target')
        
        # User commands
        user_parser = subparsers.add_parser('user', help='User operations')
        user_subparsers = user_parser.add_subparsers(dest='user_command', help='User command')
        
        # Website management
        website_parser = user_subparsers.add_parser('website', help='Website management')
        website_subparsers = website_parser.add_subparsers(dest='website_command', help='Website command')
        
        # Website management (continuing from where we left off)
        website_create = website_subparsers.add_parser('create', help='Create a new website')
        website_create.add_argument('--domain', required=True, help='Domain name')
        website_create.add_argument('--type', required=True, choices=['static', 'php', 'python', 'django', 'node'], help='Website type')
        website_create.add_argument('--ssl', action='store_true', default=True, help='Enable SSL/TLS')
        
        website_delete = website_subparsers.add_parser('delete', help='Delete a website')
        website_delete.add_argument('--domain', required=True, help='Domain name')
        
        website_list = website_subparsers.add_parser('list', help='List all websites')
        
        website_enable = website_subparsers.add_parser('enable', help='Enable a website')
        website_enable.add_argument('--domain', required=True, help='Domain name')
        
        website_disable = website_subparsers.add_parser('disable', help='Disable a website')
        website_disable.add_argument('--domain', required=True, help='Domain name')
        
        # Database management
        db_parser = user_subparsers.add_parser('database', help='Database management')
        db_subparsers = db_parser.add_subparsers(dest='db_command', help='Database command')
        
        db_create = db_subparsers.add_parser('create', help='Create a new database')
        db_create.add_argument('--name', required=True, help='Database name')
        db_create.add_argument('--type', required=True, choices=['mysql', 'postgresql', 'mongodb'], help='Database type')
        db_create.add_argument('--user', required=True, help='Database user')
        db_create.add_argument('--password', required=True, help='Database password')
        
        db_delete = db_subparsers.add_parser('delete', help='Delete a database')
        db_delete.add_argument('--name', required=True, help='Database name')
        db_delete.add_argument('--type', required=True, choices=['mysql', 'postgresql', 'mongodb'], help='Database type')
        
        db_list = db_subparsers.add_parser('list', help='List all databases')
        db_list.add_argument('--type', help='Filter by database type')
        
        db_user_add = db_subparsers.add_parser('user-add', help='Add a database user')
        db_user_add.add_argument('--name', required=True, help='Database name')
        db_user_add.add_argument('--type', required=True, choices=['mysql', 'postgresql', 'mongodb'], help='Database type')
        db_user_add.add_argument('--user', required=True, help='Username')
        db_user_add.add_argument('--password', required=True, help='Password')
        db_user_add.add_argument('--privileges', default='read,write', help='Comma-separated privileges')
        
        db_user_remove = db_subparsers.add_parser('user-remove', help='Remove a database user')
        db_user_remove.add_argument('--name', required=True, help='Database name')
        db_user_remove.add_argument('--type', required=True, choices=['mysql', 'postgresql', 'mongodb'], help='Database type')
        db_user_remove.add_argument('--user', required=True, help='Username')
        
        # Mail management
        mail_parser = user_subparsers.add_parser('mail', help='Mail management')
        mail_subparsers = mail_parser.add_subparsers(dest='mail_command', help='Mail command')
        
        mail_domain_add = mail_subparsers.add_parser('domain-add', help='Add a mail domain')
        mail_domain_add.add_argument('--domain', required=True, help='Domain name')
        
        mail_domain_remove = mail_subparsers.add_parser('domain-remove', help='Remove a mail domain')
        mail_domain_remove.add_argument('--domain', required=True, help='Domain name')
        
        mail_account_add = mail_subparsers.add_parser('account-add', help='Add a mail account')
        mail_account_add.add_argument('--email', required=True, help='Email address')
        mail_account_add.add_argument('--password', required=True, help='Password')
        mail_account_add.add_argument('--quota', type=int, default=1024, help='Quota in MB')
        
        mail_account_remove = mail_subparsers.add_parser('account-remove', help='Remove a mail account')
        mail_account_remove.add_argument('--email', required=True, help='Email address')
        
        mail_alias_add = mail_subparsers.add_parser('alias-add', help='Add a mail alias')
        mail_alias_add.add_argument('--source', required=True, help='Source email address')
        mail_alias_add.add_argument('--destination', required=True, help='Destination email address')
        
        mail_alias_remove = mail_subparsers.add_parser('alias-remove', help='Remove a mail alias')
        mail_alias_remove.add_argument('--source', required=True, help='Source email address')
        mail_alias_remove.add_argument('--destination', required=True, help='Destination email address')
        
        mail_list_add = mail_subparsers.add_parser('list-add', help='Add a mailing list')
        mail_list_add.add_argument('--name', required=True, help='List name')
        mail_list_add.add_argument('--domain', required=True, help='Domain name')
        
        mail_list_remove = mail_subparsers.add_parser('list-remove', help='Remove a mailing list')
        mail_list_remove.add_argument('--name', required=True, help='List name')
        mail_list_remove.add_argument('--domain', required=True, help='Domain name')
        
        mail_list = mail_subparsers.add_parser('list', help='List mail domains, accounts, aliases, and lists')
        mail_list.add_argument('--type', choices=['domains', 'accounts', 'aliases', 'lists'], help='Type to list')
        
        # DNS management
        dns_parser = user_subparsers.add_parser('dns', help='DNS management')
        dns_subparsers = dns_parser.add_subparsers(dest='dns_command', help='DNS command')
        
        dns_domain_add = dns_subparsers.add_parser('domain-add', help='Add a DNS domain')
        dns_domain_add.add_argument('--domain', required=True, help='Domain name')
        
        dns_domain_remove = dns_subparsers.add_parser('domain-remove', help='Remove a DNS domain')
        dns_domain_remove.add_argument('--domain', required=True, help='Domain name')
        
        dns_record_add = dns_subparsers.add_parser('record-add', help='Add a DNS record')
        dns_record_add.add_argument('--domain', required=True, help='Domain name')
        dns_record_add.add_argument('--name', required=True, help='Record name')
        dns_record_add.add_argument('--type', required=True, choices=['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'SRV'], help='Record type')
        dns_record_add.add_argument('--value', required=True, help='Record value')
        dns_record_add.add_argument('--ttl', type=int, default=3600, help='TTL in seconds')
        dns_record_add.add_argument('--priority', type=int, help='Priority (for MX and SRV records)')
        
        dns_record_remove = dns_subparsers.add_parser('record-remove', help='Remove a DNS record')
        dns_record_remove.add_argument('--domain', required=True, help='Domain name')
        dns_record_remove.add_argument('--name', required=True, help='Record name')
        dns_record_remove.add_argument('--type', required=True, choices=['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'SRV'], help='Record type')
        
        dns_list = dns_subparsers.add_parser('list', help='List DNS domains and records')
        dns_list.add_argument('--domain', help='Filter by domain')
        
        # Backup management for users
        backup_parser = user_subparsers.add_parser('backup', help='Backup management')
        backup_subparsers = backup_parser.add_subparsers(dest='backup_command', help='Backup command')
        
        backup_create = backup_subparsers.add_parser('create', help='Create a backup')
        backup_create.add_argument('--type', required=True, choices=['full', 'website', 'database', 'mail'], help='Backup type')
        backup_create.add_argument('--target', help='Target to backup (domain, database name, etc.)')
        
        backup_restore = backup_subparsers.add_parser('restore', help='Restore from backup')
        backup_restore.add_argument('--id', required=True, help='Backup ID')
        
        backup_list = backup_subparsers.add_parser('list', help='List backups')
        backup_list.add_argument('--type', help='Filter by backup type')
        
        # SFTP/FTP/SSH user management
        access_parser = user_subparsers.add_parser('access', help='Access management (SFTP/FTP/SSH)')
        access_subparsers = access_parser.add_subparsers(dest='access_command', help='Access command')
        
        access_add = access_subparsers.add_parser('add', help='Add an access user')
        access_add.add_argument('--username', required=True, help='Username')
        access_add.add_argument('--password', required=True, help='Password')
        access_add.add_argument('--type', required=True, choices=['sftp', 'ftp', 'ssh'], help='Access type')
        access_add.add_argument('--resource', required=True, help='Resource (website domain, etc.)')
        
        access_remove = access_subparsers.add_parser('remove', help='Remove an access user')
        access_remove.add_argument('--username', required=True, help='Username')
        access_remove.add_argument('--type', required=True, choices=['sftp', 'ftp', 'ssh'], help='Access type')
        
        access_list = access_subparsers.add_parser('list', help='List access users')
        access_list.add_argument('--type', help='Filter by access type')
        
        # Resource sharing
        share_parser = user_subparsers.add_parser('share', help='Resource sharing')
        share_subparsers = share_parser.add_subparsers(dest='share_command', help='Share command')
        
        share_add = share_subparsers.add_parser('add', help='Share a resource')
        share_add.add_argument('--resource', required=True, help='Resource to share')
        share_add.add_argument('--type', required=True, choices=['mount', 'tunnel'], help='Share type')
        share_add.add_argument('--target-user', required=True, help='Target user')
        share_add.add_argument('--path', help='Path to share (for mount)')
        share_add.add_argument('--port', type=int, help='Port to tunnel')
        
        # Continuing from where we left off
        share_remove = share_subparsers.add_parser('remove', help='Remove a shared resource')
        share_remove.add_argument('--resource', required=True, help='Resource to unshare')
        share_remove.add_argument('--type', required=True, choices=['mount', 'tunnel'], help='Share type')
        share_remove.add_argument('--target-user', required=True, help='Target user')
        
        share_list = share_subparsers.add_parser('list', help='List shared resources')
        share_list.add_argument('--direction', choices=['incoming', 'outgoing'], help='Filter by direction')
        
        # Daemon commands
        daemon_parser = subparsers.add_parser('daemon', help='Daemon operations')
        daemon_subparsers = daemon_parser.add_subparsers(dest='daemon_command', help='Daemon command')
        
        daemon_start = daemon_subparsers.add_parser('start', help='Start the UP daemon')
        daemon_start.add_argument('--foreground', action='store_true', help='Run in foreground')
        
        daemon_stop = daemon_subparsers.add_parser('stop', help='Stop the UP daemon')
        
        daemon_status = daemon_subparsers.add_parser('status', help='Check daemon status')
        
        daemon_check = daemon_subparsers.add_parser('check', help='Run environment checks')
        daemon_check.add_argument('--type', choices=['all', 'security', 'performance', 'health'], default='all', help='Check type')
        
        daemon_repair = daemon_subparsers.add_parser('repair', help='Repair environment issues')
        daemon_repair.add_argument('--auto', action='store_true', help='Automatically repair all issues')
        daemon_repair.add_argument('--issue-id', help='Repair specific issue')
        
        daemon_logs = daemon_subparsers.add_parser('logs', help='View daemon logs')
        daemon_logs.add_argument('--lines', type=int, default=100, help='Number of lines to show')
        daemon_logs.add_argument('--follow', action='store_true', help='Follow log output')
        
    def handle(self, *args, **options):
        """
        Main command handler that processes all subcommands
        """
        if not options['command']:
            self.print_help('manage.py', 'up')
            return
            
        # Process admin commands
        if options['command'] == 'admin':
            self._handle_admin_commands(options)
        # Process user commands
        elif options['command'] == 'user':
            self._handle_user_commands(options)
        # Process daemon commands
        elif options['command'] == 'daemon':
            self._handle_daemon_commands(options)
        else:
            self.stdout.write(self.style.ERROR(f"Unknown command: {options['command']}"))
            
    def _handle_admin_commands(self, options):
        """Handle all admin-related commands"""
        if not options['admin_command']:
            self.stdout.write(self.style.ERROR("No admin command specified"))
            return
            
        # Nginx management
        if options['admin_command'] == 'nginx':
            self._handle_nginx_commands(options)
        # VM management
        elif options['admin_command'] == 'vm':
            self._handle_vm_commands(options)
        # Container management
        elif options['admin_command'] == 'container':
            self._handle_container_commands(options)
        # Storage management
        elif options['admin_command'] == 'storage':
            self._handle_storage_commands(options)
        # User management
        elif options['admin_command'] == 'user':
            self._handle_admin_user_commands(options)
        # Backup management
        elif options['admin_command'] == 'backup':
            self._handle_admin_backup_commands(options)
        # Mount management
        elif options['admin_command'] == 'mount':
            self._handle_mount_commands(options)
        else:
            self.stdout.write(self.style.ERROR(f"Unknown admin command: {options['admin_command']}"))
            
    def _handle_nginx_commands(self, options):
        """Handle Nginx-related commands"""
        if options['nginx_command'] == 'add':
            try:
                nginx_manager.add_proxy(options['ip'], options['domain'])
                self.stdout.write(self.style.SUCCESS(f"Added Nginx proxy for {options['domain']} on {options['ip']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to add Nginx proxy: {str(e)}"))
        elif options['nginx_command'] == 'remove':
            try:
                nginx_manager.remove_proxy(options['ip'])
                self.stdout.write(self.style.SUCCESS(f"Removed Nginx proxy for {options['ip']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to remove Nginx proxy: {str(e)}"))
        elif options['nginx_command'] == 'list':
            try:
                proxies = nginx_manager.list_proxies()
                if proxies:
                    self.stdout.write(self.style.SUCCESS("Nginx proxies:"))
                    for proxy in proxies:
                        self.stdout.write(f"  {proxy['ip']} -> {proxy['domain']}")
                else:
                    self.stdout.write("No Nginx proxies configured")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to list Nginx proxies: {str(e)}"))
        else:
            self.stdout.write(self.style.ERROR(f"Unknown Nginx command: {options['nginx_command']}"))
            
    def _handle_vm_commands(self, options):
        """Handle VM-related commands"""
        if options['vm_command'] == 'create':
            try:
                vm_manager.create_vm(
                    options['name'],
                    options['hypervisor'],
                    options['memory'],
                    options['vcpus'],
                    options['disk'],
                    options['image']
                )
                self.stdout.write(self.style.SUCCESS(f"Created VM {options['name']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to create VM: {str(e)}"))
        elif options['vm_command'] == 'delete':
            try:
                vm_manager.delete_vm(options['name'])
                self.stdout.write(self.style.SUCCESS(f"Deleted VM {options['name']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to delete VM: {str(e)}"))
        elif options['vm_command'] == 'list':
            try:
                vms = vm_manager.list_vms(options.get('hypervisor'))
                if vms:
                    self.stdout.write(self.style.SUCCESS("Virtual machines:"))
                    for vm in vms:
                        self.stdout.write(f"  {vm['name']} ({vm['hypervisor']}) - {vm['status']}")
                else:
                    self.stdout.write("No virtual machines found")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to list VMs: {str(e)}"))
        elif options['vm_command'] == 'start':
            try:
                vm_manager.start_vm(options['name'])
                self.stdout.write(self.style.SUCCESS(f"Started VM {options['name']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to start VM: {str(e)}"))
        elif options['vm_command'] == 'stop':
            try:
                vm_manager.stop_vm(options['name'])
                self.stdout.write(self.style.SUCCESS(f"Stopped VM {options['name']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to stop VM: {str(e)}"))
        elif options['vm_command'] == 'resize':
            try:
                vm_manager.resize_vm(
                    options['name'],
                    options.get('memory'),
                    options.get('vcpus'),
                    options.get('disk')
                )
                self.stdout.write(self.style.SUCCESS(f"Resized VM {options['name']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to resize VM: {str(e)}"))
        else:
            self.stdout.write(self.style.ERROR(f"Unknown VM command: {options['vm_command']}"))
    
    # Similar handler methods would be implemented for other command types
    # For brevity, I'm not including all of them, but they would follow the same pattern
    
    def _handle_user_commands(self, options):
        """Handle user-facing commands"""
        if not options['user_command']:
            self.stdout.write(self.style.ERROR("No user command specified"))
            return
            
        # Website management
        if options['user_command'] == 'website':
            self._handle_website_commands(options)
        # Database management
        elif options['user_command'] == 'database':
            self._handle_database_commands(options)
        # Mail management
        elif options['user_command'] == 'mail':
            self._handle_mail_commands(options)
        # DNS management
        elif options['user_command'] == 'dns':
            self._handle_dns_commands(options)
        # Backup management
        elif options['user_command'] == 'backup':
            self._handle_user_backup_commands(options)
        # Access management
        elif options['user_command'] == 'access':
            self._handle_access_commands(options)
        # Resource sharing
        elif options['user_command'] == 'share':
            self._handle_share_commands(options)
        else:
            self.stdout.write(self.style.ERROR(f"Unknown user command: {options['user_command']}"))
    
    def _handle_daemon_commands(self, options):
        """Handle daemon-related commands"""
        if not options['daemon_command']:
            self.stdout.write(self.style.ERROR("No daemon command specified"))
            return
            
        if options['daemon_command'] == 'start':
            try:
                if options.get('foreground'):
                    self.stdout.write("Starting UP daemon in foreground mode...")
                    # Run the daemon in foreground
                    self._run_daemon_foreground()
                else:
                    # Start the daemon as a background service
                    from up_core.daemon.service import start_daemon
                    start_daemon()
                    self.stdout.write(self.style.SUCCESS("UP daemon started"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to start daemon: {str(e)}"))
        elif options['daemon_command'] == 'stop':
            try:
                from up_core.daemon.service import stop_daemon
                stop_daemon()
                self.stdout.write(self.style.SUCCESS("UP daemon stopped"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to stop daemon: {str(e)}"))
        elif options['daemon_command'] == 'status':
            try:
                from up_core.daemon.service import daemon_status
                status = daemon_status()
                if status['running']:
                    self.stdout.write(self.style.SUCCESS(f"UP daemon is running (PID: {status['pid']})"))
                    self.stdout.write(f"Uptime: {status['uptime']}")
                    self.stdout.write(f"Monitored resources: {status['resources']}")
                else:
                    self.stdout.write("UP daemon is not running")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to get daemon status: {str(e)}"))
        elif options['daemon_command'] == 'check':
            try:
                check_type = options.get('type', 'all')
                self.stdout.write(f"Running {check_type} checks...")
                
                if check_type == 'all' or check_type == 'security':
                    security_issues = security_monitor.check_security()
                    if security_issues:
                        self.stdout.write(self.style.WARNING(f"Found {len(security_issues)} security issues:"))
                        for issue in security_issues:
                            self.stdout.write(f"  [{issue['id']}] {issue['severity']}: {issue['description']}")
                    else:
                        self.stdout.write(self.style.SUCCESS("No security issues found"))
                
                if check_type == 'all' or check_type == 'health':
                    health_issues = health_monitor.check_health()
                    if health_issues:
                        self.stdout.write(self.style.WARNING(f"Found {len(health_issues)} health issues:"))
                        for issue in health_issues:
                            self.stdout.write(f"  [{issue['id']}] {issue['severity']}: {issue['description']}")
                    else:
                        self.stdout.write(self.style.SUCCESS("No health issues found"))
                
                if check_type == 'all' or check_type == 'performance':
                    perf_issues = health_monitor.check_performance()
                    if perf_issues:
                        self.stdout.write(self.style.WARNING(f"Found {len(perf_issues)} performance issues:"))
                        for issue in perf_issues:
                            self.stdout.write(f"  [{issue['id']}] {issue['severity']}: {issue['description']}")
                    else:
                        self.stdout.write(self.style.SUCCESS("No performance issues found"))
                        
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to run checks: {str(e)}"))
                
        elif options['daemon_command'] == 'repair':
            try:
                if options.get('issue_id'):
                    # Repair specific issue
                    issue_id = options['issue_id']
                    self.stdout.write(f"Repairing issue {issue_id}...")
                    result = auto_repair.repair_issue(issue_id)
                    if result['success']:
                        self.stdout.write(self.style.SUCCESS(f"Successfully repaired issue {issue_id}"))
                    else:
                        self.stdout.write(self.style.ERROR(f"Failed to repair issue {issue_id}: {result['message']}"))
                elif options.get('auto'):
                    # Auto-repair all issues
                    self.stdout.write("Auto-repairing all issues...")
                    results = auto_repair.repair_all()
                    
                    success_count = sum(1 for r in results if r['success'])
                    fail_count = len(results) - success_count
                    
                    self.stdout.write(self.style.SUCCESS(f"Repaired {success_count} issues successfully"))
                    if fail_count > 0:
                        self.stdout.write(self.style.WARNING(f"Failed to repair {fail_count} issues:"))
                        for result in results:
                            if not result['success']:
                                self.stdout.write(f"  [{result['id']}]: {result['message']}")
                else:
                    self.stdout.write(self.style.ERROR("Please specify --auto or --issue-id"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to repair issues: {str(e)}"))
                
        elif options['daemon_command'] == 'logs':
            try:
                from up_core.daemon.service import get_logs, follow_logs
                lines = options.get('lines', 100)
                follow = options.get('follow', False)
                
                logs = get_logs(lines)
                for log in logs:
                    self.stdout.write(log)
                    
                if follow:
                    self.stdout.write("Following log output (Ctrl+C to stop)...")
                    try:
                        for log in follow_logs():
                            self.stdout.write(log)
                    except KeyboardInterrupt:
                        self.stdout.write("Stopped following logs")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to get logs: {str(e)}"))
                logger.error(f"Failed to get logs: {str(e)}", exc_info=True)
        else:
            self.stdout.write(self.style.ERROR(f"Unknown daemon command: {options['daemon_command']}"))
    
    def _run_daemon_foreground(self):
        """Run the daemon in foreground mode"""
        try:
            from up_core.daemon import health_monitor, security_monitor, auto_repair
            
            self.stdout.write("Starting health monitoring...")
            health_monitor.start()
            
            self.stdout.write("Starting security monitoring...")
            security_monitor.start()
            
            self.stdout.write("Starting auto-repair service...")
            auto_repair.start()
            
            self.stdout.write(self.style.SUCCESS("UP daemon running in foreground mode (Ctrl+C to stop)"))
            
            # Keep the process running until interrupted
            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stdout.write("Stopping daemon services...")
                auto_repair.stop()
                security_monitor.stop()
                health_monitor.stop()
                self.stdout.write(self.style.SUCCESS("UP daemon stopped"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error in daemon: {str(e)}"))
            logger.error(f"Daemon error: {str(e)}", exc_info=True)
    
    def _handle_container_commands(self, options):
        """Handle container-related commands"""
        if options['container_command'] == 'create':
            try:
                container_manager.create_container(
                    options['name'],
                    options['host'],
                    options['image'],
                    options['user'],
                    options.get('memory'),
                    options.get('cpu')
                )
                self.stdout.write(self.style.SUCCESS(f"Created container {options['name']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to create container: {str(e)}"))
        elif options['container_command'] == 'delete':
            try:
                container_manager.delete_container(options['name'], options['host'])
                self.stdout.write(self.style.SUCCESS(f"Deleted container {options['name']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to delete container: {str(e)}"))
        elif options['container_command'] == 'list':
            try:
                containers = container_manager.list_containers(
                    options.get('host'),
                    options.get('user')
                )
                if containers:
                    self.stdout.write(self.style.SUCCESS("Containers:"))
                    for container in containers:
                        self.stdout.write(f"  {container['name']} ({container['host']}) - {container['status']}")
                else:
                    self.stdout.write("No containers found")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to list containers: {str(e)}"))
        else:
            self.stdout.write(self.style.ERROR(f"Unknown container command: {options['container_command']}"))
    
    def _handle_storage_commands(self, options):
        """Handle storage-related commands"""
        if options['storage_command'] == 'create':
            try:
                storage_manager.create_storage(
                    options['name'],
                    options['type'],
                    options['size'],
                    options['host']
                )
                self.stdout.write(self.style.SUCCESS(f"Created {options['type']} storage {options['name']} ({options['size']} GB)"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to create storage: {str(e)}"))
        elif options['storage_command'] == 'attach':
            try:
                storage_manager.attach_storage(
                    options['storage'],
                    options['target'],
                    options['mount']
                )
                self.stdout.write(self.style.SUCCESS(f"Attached storage {options['storage']} to {options['target']} at {options['mount']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to attach storage: {str(e)}"))
        elif options['storage_command'] == 'detach':
            try:
                storage_manager.detach_storage(
                    options['storage'],
                    options['target']
                )
                self.stdout.write(self.style.SUCCESS(f"Detached storage {options['storage']} from {options['target']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to detach storage: {str(e)}"))
        elif options['storage_command'] == 'list':
            try:
                storages = storage_manager.list_storages()
                if storages:
                    self.stdout.write(self.style.SUCCESS("Storage volumes:"))
                    for storage in storages:
                        self.stdout.write(f"  {storage['name']} ({storage['type']}, {storage['size']} GB) - {storage['status']}")
                        if storage.get('attachments'):
                            for attachment in storage['attachments']:
                                self.stdout.write(f"    → Attached to {attachment['target']} at {attachment['mount']}")
                else:
                    self.stdout.write("No storage volumes found")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to list storage volumes: {str(e)}"))
        else:
            self.stdout.write(self.style.ERROR(f"Unknown storage command: {options['storage_command']}"))
    
    def _handle_website_commands(self, options):
        """Handle website-related commands"""
        if options['website_command'] == 'create':
            try:
                website_manager.create_website(
                    options['domain'],
                    options['type'],
                    options.get('ssl', True)
                )
                self.stdout.write(self.style.SUCCESS(f"Created {options['type']} website for {options['domain']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to create website: {str(e)}"))
        elif options['website_command'] == 'delete':
            try:
                website_manager.delete_website(options['domain'])
                self.stdout.write(self.style.SUCCESS(f"Deleted website {options['domain']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to delete website: {str(e)}"))
        elif options['website_command'] == 'list':
            try:
                websites = website_manager.list_websites()
                if websites:
                    self.stdout.write(self.style.SUCCESS("Websites:"))
                    for website in websites:
                        ssl_status = "SSL enabled" if website.get('ssl') else "SSL disabled"
                        self.stdout.write(f"  {website['domain']} ({website['type']}) - {website['status']} - {ssl_status}")
                else:
                    self.stdout.write("No websites found")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to list websites: {str(e)}"))
        elif options['website_command'] == 'enable':
            try:
                website_manager.enable_website(options['domain'])
                self.stdout.write(self.style.SUCCESS(f"Enabled website {options['domain']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to enable website: {str(e)}"))
        elif options['website_command'] == 'disable':
            try:
                website_manager.disable_website(options['domain'])
                self.stdout.write(self.style.SUCCESS(f"Disabled website {options['domain']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to disable website: {str(e)}"))