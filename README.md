# UP - Secure Hosting Environment Management Tool

UP is a comprehensive secure hosting environment management tool built with Django that provides centralized management for containerized applications, websites, and infrastructure resources.

## Overview

UP enables administrators and users to manage a complete hosting infrastructure through a unified CLI interface (`up` command) with API access. The system is designed with security and isolation in mind, using containerized workloads and proper user separation.

## Architecture

The system follows a layered architecture:
Client Requests → Firewall → Nginx Reverse Proxy → VMs/Containers → Services

- **Frontend Layer**: Nginx reverse proxy handling static files and request forwarding
- **Compute Layer**: Hypervisors running VMs with Podman containers
- **Management Layer**: Central Django-based management system
- **Monitoring Layer**: Automated health checks and security monitoring

## Features

### For Administrators
- **Infrastructure Management**
  - Nginx reverse proxy management for IP groups
  - Libvirtd service connections (local/remote)
  - VM lifecycle management (create, move, reboot, resize, destroy)
  - Hypervisor and network updates
  - Container management with Podman
  - Storage management for libvirt and containerd
  - User management and access control

- **Operations**
  - Backup/restore functions
  - Dynamic file mounting to VMs and containers
  - Remote share and disk mounting
  - Environment maintenance and updates

### For Users
- **Website Management**
  - Create, delete, and edit websites using Ansible playbooks and Jinja templates
  - SSL/TLS certificate management with Certbot
  - Subdomain assignment from wildcard domains

- **Database Management**
  - Database and user creation/management
  - Flexible database-user pairing
  - Local data storage

- **Communication Services**
  - Mail domain, address, alias, and list management
  - DNS domain and record management with RFC2136
  - Local data storage with external synchronization

- **Access Management**
  - SFTP, FTP, SSH user management for owned resources
  - Direct container access
  - Resource sharing between containers (mutual enablement required)

- **Backup Services**
  - Full and partial backup initiation
  - User-controlled backup scheduling

### Daemon Services
- **Auto-Maintenance**
  - Continuous environment health monitoring
  - Automatic issue detection and repair
  - Alert system for unresolvable issues

- **Security Monitoring**
  - Log analysis and security monitoring
  - Automated security checks
  - Threat detection and response

## Security Features

- **SSL/TLS Everywhere**: All services use SSL/TLS with Certbot-managed certificates
- **User Isolation**: Complete separation between user resources
- **Access Control**: Users can only access their own resources locally
- **Public Interface**: Cross-user access only through public interfaces
- **Dynamic User Mapping**: Secure user-to-container mapping

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd up
```
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Configure Django settings:
```bash
python manage.py migrate
```
4. Create a superuser:
```bash
python manage.py createsuperuser
```
## Usage
### CLI Interface
The main interface is through the up command:
```bash
# Admin operations
python manage.py up admin <command>
python manage.py up nginx <command>
python manage.py up vm <command>

# User operations
python manage.py up user <command>
python manage.py up website <command>
python manage.py up container <command>

# Daemon operations
python manage.py up daemon <command>
```
### API Access
The system provides REST API endpoints for all operations, enabling integration 
with external tools and future GUI development.
### Web Interface
Access the Django admin interface at /admin/ for basic management tasks.
## Development Roadmap
### Planned Features
- High Availability: Automated failover recovery and anti-affinity options
- Resource Optimization: Automated resource assignment and merging
- Maintenance Mode: Label-based maintenance scheduling
- AI Integration: LocalAI for log and security monitoring
- GUI: Modern React/Node.js frontend
- Enhanced Monitoring: Advanced security and performance monitoring
### Current Status
 - ✅ Core Django framework
 - ✅ CLI command structure
 - ✅ Basic daemon services
 - ✅ Auto-repair functionality
 - 🚧 Container management
 - 🚧 VM management
 - 🚧 User management
 - 🚧 Website management
## Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request
## License
GNU GENERAL PUBLIC LICENSE Version 3
## Support
For issues and questions, please use the GitHub issue tracker.
```