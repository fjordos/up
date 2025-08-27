#!/bin/bash
set -e

VM_NAME="${VM_NAME:-vm-default}"
MEMORY_GB="${MEMORY_GB:-2}"
VCPUS="${VCPUS:-2}"
DISK_SIZE_GB="${DISK_SIZE_GB:-20}"
VM_OS="${VM_OS:-centos-stream10}"

# Paths and configuration
DISK_PATH="/var/lib/libvirt/images/${VM_NAME}.qcow2"
VM_HOSTNAME="${VM_NAME}.${HOST_DOMAINNAME:=$(hostname)}"
SHARED_IP="${DEFAULT_SHARED_IP:-192.168.122.1}"
SHARED_DIR="${BASE_SHARED_DIR:-/mnt}/${VM_NAME}"
NETWORK_NAME="${DEFAULT_NETWORK_NAME:-default}"
VM_DATA_DIR="/var/lib/libvirt/data/${VM_NAME}"
CLOUD_IMAGES_DIR="/var/lib/libvirt/images/cloud"
CAN_DELETE=${CAN_DELETE:-1}

# Cloud image URLs
declare -A CLOUD_IMAGES=(
    ["ubuntu-22.04"]="https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
    ["ubuntu-20.04"]="https://cloud-images.ubuntu.com/focal/current/focal-server-cloudimg-amd64.img"
    ["debian-12"]="https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2"
    ["centos-stream9"]="https://cloud.centos.org/centos/9-stream/x86_64/images/CentOS-Stream-GenericCloud-9-latest.x86_64.qcow2"
    ["centos-stream10"]="https://cloud.centos.org/centos/10-stream/x86_64/images/CentOS-Stream-GenericCloud-x86_64-10-latest.x86_64.qcow2"
    ["fedora-42"]="https://download.fedoraproject.org/pub/fedora/linux/releases/42/Cloud/x86_64/images/Fedora-Cloud-Base-Generic-42-1.1.x86_64.qcow2"
)

prepare_main() {
  local PREP=""
  for P in virt-install qemu-img ; do
    [[ $(which $P > /dev/null 2>&1) ]] || PREP="$PREP $P"
  done
  [[ -e /usr/bin/virsh ]] || PREP="$PREP libvirt-client"
  [[ -e /usr/sbin/libvirtd ]] || PREP="$PREP libvirt-daemon libvirt-daemon-kvm"
  if [[ -z "$PREP" ]]; then
    sudo yum -y install $PREP
  fi
}

# Function to get network details
get_network_info() {
    local network="$1"
    local network_xml=$(virsh net-dumpxml "$network" 2>/dev/null)

    # Extract network range
    local ip_range=$(echo "$network_xml" | xmllint --xpath "string(//ip/@address)" -)
    local netmask=$(echo "$network_xml" | xmllint --xpath "string(//ip/@netmask)" -)
    local dhcp_start=$(echo "$network_xml" | xmllint --xpath "string(//dhcp/range/@start)" -)
    local dhcp_end=$(echo "$network_xml" | xmllint --xpath "string(//dhcp/range/@end)" -)

    echo "$ip_range|$netmask|$dhcp_start|$dhcp_end"
}

# Function to get next available IP
get_next_available_ip() {
    local network="$1"

    # Get network configuration
    local network_info=$(get_network_info "$network")
    IFS='|' read -r network_ip netmask dhcp_start dhcp_end <<< "$network_info"

    if [[ -z "$dhcp_start" || -z "$dhcp_end" ]]; then
        echo "ERROR: Could not determine DHCP range for network $network" >&2
        return 1
    fi

    # Extract base IP and range
    local base_ip=$(echo "$dhcp_start" | cut -d. -f1-3)
    local start_host=$(echo "$dhcp_start" | cut -d. -f4)
    local end_host=$(echo "$dhcp_end" | cut -d. -f4)

    logger "Checking IP range: ${dhcp_start} - ${dhcp_end}" >&2

    # Get existing DHCP reservations
    local existing_ips=$(virsh net-dumpxml "$network" 2>/dev/null | grep -oP "ip='\K[^']*" | sort -V)

    # Check each IP in the DHCP range
    for i in $(seq $start_host $end_host); do
        local test_ip="${base_ip}.$i"

        # Check if IP is already reserved
        if echo "$existing_ips" | grep -q "^$test_ip$"; then
            continue
        fi

        # Check if IP is currently in use (ping test)
        if ping -c 1 -W 1 "$test_ip" >/dev/null 2>&1; then
            continue
        fi

        # Found available IP
        echo "$test_ip"
        return 0
    done

    echo "ERROR: No available IP found in DHCP range ${dhcp_start}-${dhcp_end}" >&2
    return 1
}

# Function to generate unique SSH key for VM
generate_vm_ssh_key() {
    local vm_name="$1"
    local ssh_dir="/var/lib/libvirt/cloud-init/${vm_name}"
    local private_key="$ssh_dir/id_rsa"
    local public_key="$ssh_dir/id_rsa.pub"

    # Create SSH keys directory
    mkdir -p "$ssh_dir"
    chmod 700 "$ssh_dir"

    # Generate SSH key pair if it doesn't exist
    if [[ ! -f "$private_key" ]]; then
        logger "Generating unique SSH key for VM: $vm_name"
        ssh-keygen -t rsa -b 4096 -f "$private_key" -N "" -C "vm-${vm_name}@$(hostname)"
        chmod 600 "$private_key"
        chmod 644 "$public_key"
        logger "✓ SSH key generated: $private_key"
    else
        logger "SSH key already exists: $private_key"
    fi

    # Return the public key content
    cat "$public_key"
}

# Function to download cloud image
download_cloud_image() {
    local image_name="$1"
    local image_url="${CLOUD_IMAGES[$image_name]}"

    if [[ -z "$image_url" ]]; then
        echo "ERROR: Unknown cloud image: $image_name"
        echo "Available images: ${!CLOUD_IMAGES[@]}"
        exit 1
    fi

    local image_file="$CLOUD_IMAGES_DIR/$(basename "$image_url")"

    mkdir -p "$CLOUD_IMAGES_DIR"
    if [[ ! -f "$image_file" ]]; then
        wget --quiet -O "$image_file" "$image_url"
    fi

    echo "$image_file"
}

# Function to create cloud-init user-data (updated)
create_user_data() {
    local vm_name="$1"
    local vm_hostname="$2"
    local ssh_public_key="$3"

    cat > "$VM_DATA_DIR/user-data" << EOF
#cloud-config
hostname: $vm_hostname
fqdn: ${vm_hostname}.local

# Default user configuration
users:
  - name: admin
    groups: wheel
    shell: /bin/bash
    ssh_authorized_keys:
      - $ssh_public_key

# Package management
package_update: true
package_upgrade: true
packages:
  - qemu-guest-agent
  - curl
  - wget
  - vim
  - net-tools
  - fail2ban
  - ktls-utils
  - cachefilesd

# SSH configuration
ssh_pwauth: false
disable_root: true
ssh_authorized_keys:
  - $ssh_public_key

# Security configuration
runcmd:
  - mkdir -p /var/lib/shared/host
  - systemctl enable --now qemu-guest-agent
  - systemctl enable --now fail2ban
  - firewall-cmd --permanent --add-service ssh
  - firewall-cmd --permanent --add-service http
  - firewall-cmd --permanent --add-service https
  - firewall-cmd --reload
  - echo "ChallengeResponseAuthentication no" >> /etc/ssh/sshd_config
  - echo "PasswordAuthentication no" >> /etc/ssh/sshd_config
  - echo "PubkeyAuthentication yes" >> /etc/ssh/sshd_config
  - echo "PermitRootLogin no" >> /etc/ssh/sshd_config
  - systemctl reload ssh
  - echo "${SHARED_IP} ${HOST_DOMAINNAME}" >> /etc/hosts
  - systemctl enable --now cachefilesd
  - systemctl enable --now tlshd.service

# Network configuration
write_files:
  - path: /etc/netplan/01-netcfg.yaml
    content: |
      network:
        version: 2
        ethernets:
          enp1s0:
            dhcp4: true
    permissions: '0644'
  - path: /etc/ssh/banner
    content: |
      =====================================
      Welcome to VM: $vm_hostname
      =====================================
      This system is for authorized users only.
      All activity is logged and monitored.
      =====================================
    permissions: '0644'
  - path: /etc/sudoers.d/wheel
    content: |
      %wheel  ALL=(ALL)       NOPASSWD: ALL
    owner: root:root
    permissions: '0440'

mounts:
- [ /mnt, ${HOST_DOMAINNAME}:${SHARED_DIR}, nfs4, fsc,nfsvers=4.2,xprtsec=tls ]

# Final message
final_message: "Cloud-init setup complete for $vm_hostname with unique SSH key"
phone_home:
  post: all
  url: "https://www.up024.com/phone_home"

# Power state
power_state:
  mode: reboot
  delay: "+1"
  message: "Rebooting after cloud-init setup"
EOF
}

# Function to create cloud-init meta-data
create_meta_data() {
    local vm_name="$1"
    local vm_hostname="$2"

    cat > "$VM_DATA_DIR/meta-data" << EOF
instance-id: $vm_name
local-hostname: $vm_hostname
EOF
}

# Function to create cloud-init network config
create_network_config() {
    local vm_ip="$1"

    cat > "$VM_DATA_DIR/network-config" << EOF
version: 2
ethernets:
  enp1s0:
    dhcp4: true
    dhcp-identifier: mac
EOF
}

# Enhanced function to safely manage SSH config entries
manage_ssh_config_entry() {
    local action="$1"  # add, update, remove
    local vm_name="$2"
    local vm_ip="$3"
    local ssh_key="$4"

    local ssh_config="$HOME/.ssh/config"
    local backup_file="$HOME/.ssh/config.backup.$(date +%Y%m%d_%H%M%S)"
    local temp_file="/tmp/ssh_config_temp.$$"

    # Create backup
    cp "$ssh_config" "$backup_file" 2>/dev/null || touch "$ssh_config"

    case "$action" in
        "add")
            # Check if entry already exists
            if grep -q "^Host $vm_name$" "$ssh_config" 2>/dev/null; then
                echo "SSH config entry for $vm_name already exists. Use 'update' to modify."
                return 1
            fi

            cat >> "$ssh_config" << EOF

Host $vm_name
    HostName $vm_ip
    User admin
    IdentityFile $ssh_key
    StrictHostKeyChecking yes
    PasswordAuthentication no
    PubkeyAuthentication yes
EOF
            logger "✓ Added SSH config entry for $vm_name"
            ;;

        "update")
            if ! grep -q "^Host $vm_name$" "$ssh_config" 2>/dev/null; then
                echo "SSH config entry for $vm_name not found. Use 'add' to create."
                return 1
            fi

            # Remove existing entry and add new one
            awk -v host="$vm_name" '
                BEGIN { skip = 0 }
                /^Host / {
                    if ($2 == host) {
                        skip = 1
                        next
                    } else {
                        skip = 0
                    }
                }
                /^Host / && skip == 1 { skip = 0 }
                skip == 0 { print }
                /^$/ && skip == 1 { skip = 0 }
            ' "$ssh_config" > "$temp_file"

            # Add updated entry
            cat >> "$temp_file" << EOF

Host $vm_name
    HostName $vm_ip
    User admin
    IdentityFile $ssh_key
    StrictHostKeyChecking yes
    PasswordAuthentication no
    PubkeyAuthentication yes
EOF

            mv "$temp_file" "$ssh_config"
            logger "✓ Updated SSH config entry for $vm_name"
            ;;

        "remove")
            if ! grep -q "^Host $vm_name$" "$ssh_config" 2>/dev/null; then
                echo "SSH config entry for $vm_name not found."
                return 1
            fi

            # Remove the entry
            awk -v host="$vm_name" '
                BEGIN { skip = 0 }
                /^Host / {
                    if ($2 == host) {
                        skip = 1
                        next
                    } else {
                        skip = 0
                    }
                }
                /^Host / && skip == 1 { skip = 0 }
                skip == 0 { print }
                /^$/ && skip == 1 { skip = 0 }
            ' "$ssh_config" > "$temp_file"

            mv "$temp_file" "$ssh_config"
            logger "✓ Removed SSH config entry for $vm_name"
            ;;

        *)
            echo "Invalid action: $action. Use: add, update, remove"
            return 1
            ;;
    esac

    # Validate SSH config
    if ! ssh -F "$ssh_config" -o BatchMode=yes -o ConnectTimeout=1 nonexistent-host 2>&1 | \
         grep -q "Bad configuration option"; then
        logger "✓ SSH config is valid"
        return 0
    else
        echo "✗ Invalid SSH config, restoring backup"
        cp "$backup_file" "$ssh_config"
        return 1
    fi
}

# Function to list SSH config entries for VMs
list_ssh_config_entries() {
    local ssh_config="$HOME/.ssh/config"

    if [[ ! -f "$ssh_config" ]]; then
        echo "No SSH config file found"
        return 1
    fi

    echo "SSH Config Entries:"
    echo "==================="

    awk '
        /^Host / {
            host = $2
            hostname = ""
            user = ""
            key = ""
        }
        /^[[:space:]]*HostName/ { hostname = $2 }
        /^[[:space:]]*User/ { user = $2 }
        /^[[:space:]]*IdentityFile/ { key = $2 }
        /^Host / && NR > 1 {
            if (prev_host != "" && prev_host != "*") {
                printf "Host: %-15s IP: %-15s User: %-10s Key: %s\n", prev_host, prev_hostname, prev_user, prev_key
            }
        }
        {
            prev_host = host
            prev_hostname = hostname
            prev_user = user
            prev_key = key
        }
        END {
            if (host != "" && host != "*") {
                printf "Host: %-15s IP: %-15s User: %-10s Key: %s\n", host, hostname, user, key
            }
        }
    ' "$ssh_config"
}

logger "Creating VM: $VM_NAME"
logger "Memory: ${MEMORY_GB}GB, vCPUs: $VCPUS, Disk: ${DISK_SIZE_GB}GB"
logger "Cloud Image: $VM_OS"

mkdir -p $VM_DATA_DIR

# Download cloud image
CLOUD_IMAGE_PATH=$(download_cloud_image "$VM_OS")

# Create VM disk from cloud image
if [[ ! -f "${DISK_PATH}" ]]; then
    logger "Creating VM disk from cloud image..."
    cp "${CLOUD_IMAGE_PATH}" "${DISK_PATH}"
else
    logger "VM disk already exists: ${DISK_PATH}"
fi

# Find next available IP
logger "Finding next available IP address..."
VM_IP="${5:-$(get_next_available_ip "$NETWORK_NAME")}"

if [[ "$VM_IP" == ERROR:* ]]; then
    echo "$VM_IP"
    exit 1
fi

logger "Assigned IP: $VM_IP"

# Stop the VM if it's running
if virsh list --all | grep -q "^ $VM_NAME "; then
  if $CAN_DELETE ; then
    virsh destroy "$VM_NAME" 2>/dev/null || true
  else
    exit 1
  fi
fi

# Generate unique SSH key for VM
logger "Generating unique SSH key for VM..."
VM_SSH_PUBLIC_KEY=$(generate_vm_ssh_key "$VM_NAME")
VM_SSH_PRIVATE_KEY="/var/lib/libvirt/cloud-init/${VM_NAME}/id_rsa"

logger "✓ SSH key generated"
logger "  Public key: /var/lib/libvirt/cloud-init/${VM_NAME}/id_rsa.pub"
logger "  Private key: $VM_SSH_PRIVATE_KEY"

mkdir -p "$SHARED_DIR"

# Create cloud-init configuration
logger "Creating cloud-init configuration..."
create_user_data "$VM_NAME" "$VM_HOSTNAME" "$VM_SSH_PUBLIC_KEY"
create_meta_data "$VM_NAME" "$VM_HOSTNAME"
create_network_config "$VM_IP"
if [[ -z "$SSHCMD" ]] ; then
  VM_IP_PUB="$VM_IP"
else
  VM_IP_PUB="${HOST_IP}"
fi

logger "Create NFS directory on shared storage"
mkdir -p "$SHARED_DIR"
NEWL="${SHARED_DIR} ${VM_IP_PUB}(rw,no_root_squash,wdelay,sec=sys)"
if [[ -e "/etc/exports.d/$VM_NAME" ]]; then
  sed -i "s|^$SHARED_DIR .*|${NEWL}|" "/etc/exports.d/$VM_NAME"
  logger "✓ Updated line in /etc/exports.d/$VM_NAME: $NEWL"
else
  echo "$NEWL" > "/etc/exports.d/$VM_NAME"
  logger "✓ Inserted line in /etc/exports.d/${VM_NAME}: $NEWL"
fi
exportfs -ra

if [[ $VCPUS -eq 1 ]]; then
  CPUCORES=1
  CPUTHREADS=1
else
  CPUCORES=$((VCPUS / 2))
  VCPUS=$(($CPUCORES * 2))
  CPUTHREADS=2
fi

# Create the base VM with cloud-init
virt-install \
  --name "${VM_NAME}" \
  --memory "$((MEMORY_GB * 1024))" \
  --memorybacking "hugepages.page.size=1,hugepages.page.unit=GiB,access.mode=shared" \
  --vcpus "${VCPUS}" \
  --cpu "host-passthrough,cache.mode=passthrough,topology.sockets=1,topology.dies=1,topology.cores=${CPUCORES},topology.threads=${CPUTHREADS}" \
  --machine "q35" \
  --arch "x86_64" \
  --os-variant "${VM_OS}" \
  --disk "path=${DISK_PATH},size=${DISK_SIZE_GB},format=qcow2,bus=virtio,discard=unmap" \
  --cloud-init "user-data=${VM_DATA_DIR}/user-data,meta-data=${VM_DATA_DIR}/meta-data,network-config=${VM_DATA_DIR}/network-config,clouduser-ssh-key=${VM_SSH_PRIVATE_KEY}.pub" \
  --network "network=${NETWORK_NAME},model=virtio" \
  --graphics "vnc,listen=127.0.0.1" \
  --video "virtio" \
  --channel "unix,target.type=virtio,name=org.qemu.guest_agent.0" \
  --rng "/dev/random,model=virtio" \
  --watchdog "i6300esb,action=reset" \
  --features "acpi=on,apic=on,pmu.state=off,vmport.state=off,smm.state=on" \
  --clock "offset=utc,rtc_tickpolicy=catchup,pit_tickpolicy=delay,hpet_present=no" \
  --events "on_poweroff=destroy,on_reboot=restart,on_crash=destroy" \
  --pm "suspend_to_mem.enabled=no,suspend_to_disk.enabled=no" \
  --memballoon "model=none" \
  --import \
  --boot "hd" \
  --autostart \
  --autoconsole "none"

logger "Base VM created. Applying advanced configurations..."

logger "Apply memory backing with hugepages"
#virt-xml "$VM_NAME" --edit --memorybacking hugepages.page.size=1,hugepages.page.unit=GiB,access.mode=shared

logger "Set CPU topology to match template"
#virt-xml "$VM_NAME" --edit --cpu \
#  topology.sockets=1,topology.dies=1,topology.cores=1,topology.threads=2

logger "Add SMM feature"
#virt-xml "$VM_NAME" --edit --features smm.state=on

logger "Configure clock timers"
#virt-xml "$VM_NAME" --edit --clock \
#  timer_rtc_tickpolicy=catchup,timer_pit_tickpolicy=delay,timer_hpet_present=no

logger "Set power management"
#virt-xml "$VM_NAME" --edit --pm \
#  suspend_to_mem.enabled=no,suspend_to_disk.enabled=no

logger "Set memballoon to none"
#virt-xml "$VM_NAME" --edit --memballoon model=none

logger "Remove some unnecessary devices"
virt-xml "$VM_NAME" --remove-device --input type=tablet 2>/dev/null || true

logger "Get MAC and configure network"
VM_MAC=$(virsh dumpxml "$VM_NAME" | xmllint --xpath "string(//interface/mac/@address)" -)

logger "Configuring network mapping..."
logger "MAC: $VM_MAC"
logger "IP: $VM_IP"
logger "Hostname: $VM_HOSTNAME"

# Add DHCP reservation
if virsh net-update "$NETWORK_NAME" add ip-dhcp-host \
  "<host mac='$VM_MAC' name='$VM_HOSTNAME' ip='$VM_IP'/>" \
  --live --config 2>/dev/null; then
    logger "✓ DHCP reservation added successfully"
else
    echo "⚠ Failed to add DHCP reservation (may already exist)"
fi

echo "VM '$VM_NAME' has been created and configured successfully!"
echo "Network Configuration:"
echo "  MAC Address: $VM_MAC"
echo "  IP Address:  $VM_IP"
echo "  Hostname:    $VM_HOSTNAME"
echo "Cloud-init Configuration:"
echo "  User-data:   $VM_DATA_DIR/user-data"
echo "  Meta-data:   $VM_DATA_DIR/meta-data"
echo "  ISO:         $CLOUD_IMAGE_PATH"
echo ""

# Wait for VM to be running
echo "Waiting for VM to start..."
sleep 10

# Check VM status
VM_STATE=$(virsh domstate "$VM_NAME")
echo "VM State: $VM_STATE"

if [[ "$VM_STATE" == "running" ]]; then
    echo "✓ VM started successfully!"
    echo ""
    echo "Cloud-init will now configure the VM. This may take a few minutes."
    echo "You can monitor the progress with:"
    echo "  virsh console $VM_NAME"
    echo ""
    echo "Once cloud-init completes, you can:"
    echo "  SSH to VM:   ssh admin@$VM_IP"
    echo "  VNC access:  $(virsh vncdisplay "$VM_NAME" 2>/dev/null || echo "VNC not available")"
    echo ""
    echo "To check cloud-init status inside the VM:"
    echo "  cloud-init status"
    echo "  cloud-init status --wait"
    echo ""
    echo "Available commands:"
    echo "  Stop VM:     virsh shutdown $VM_NAME"
    echo "  Force stop:  virsh destroy $VM_NAME"
    echo "  VM info:     virsh dominfo $VM_NAME"
    echo "  VM console:  virsh console $VM_NAME (Ctrl+] to exit)"

    echo "Waiting for cloud-init to complete..."
    echo "This may take several minutes..."

    logger "Manage SSH config entry"
    if manage_ssh_config_entry "add" "$VM_NAME" "$VM_IP" "$VM_SSH_PRIVATE_KEY"; then
        logger "✓ SSH config updated. You can now connect with: ssh $VM_NAME"
    else
        if manage_ssh_config_entry "update" "$VM_NAME" "$VM_IP" "$VM_SSH_PRIVATE_KEY"; then
            echo "⚠ SSH config update failed, but you can still connect with: ssh -i $VM_SSH_PRIVATE_KEY admin@$VM_IP"
        fi
    fi
    # Try to connect and check cloud-init status
    for i in {1..60}; do
        echo -n "."
        virsh domstate "$VM_NAME" >/dev/null 2>&1
        if ping -c 1 -W 1 "$VM_IP" >/dev/null 2>&1; then
            echo ""
            echo "VM is responding to ping. Checking SSH..."
            if ssh -i "$VM_SSH_PRIVATE_KEY" -o ConnectTimeout=5 -o StrictHostKeyChecking=yes $VM_NAME "cloud-init status --wait" 2>/dev/null; then
                echo "✓ Cloud-init completed successfully!"
                logger "✓ Cloud-init completed successfully!"
                echo "VM is ready for use."
                break
            fi
        fi
        sleep 10
    done

    if [[ $i -eq 60 ]]; then
        echo ""
        echo "⚠ Timeout waiting for cloud-init. VM may still be initializing."
        logger "⚠ Timeout waiting for cloud-init. VM may still be initializing."
        echo "You can check manually with: ssh -i $VM_SSH_PRIVATE_KEY admin@$VM_IP"
    fi

else
    logger -s "✗ Failed to start VM"
    echo "Check VM status with: virsh domstate $VM_NAME"
    echo "Check VM logs with: virsh dumpxml $VM_NAME"
fi
