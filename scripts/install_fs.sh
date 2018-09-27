#!/bin/bash 

###################################################################
####    Installation / Upgrade Btrfs storage                   ####
###################################################################

 # Usage info
show_help() {
cat << EOF
 Usage: ${0##*/} [-htfms] -c <configuration_file>
 Installation / Upgrade / Uninstall FS

      -h          display this help and exit       
      -t          remove Btrfs storage and exit
            -f    force remove flag for remove option
      -c          Btrfs configuration file
      -m          Monitoring Btrfs
      -s          Stop services
EOF
}

min_kernel_version_for_btrfs="3.13"
debug_mode=0

force_remove=0
should_remove_btrfs=0
btrfs_condfiguration_filename=""
stop_services=0
is_btrfs=0
should_exit_after_btrfs_uninstall=1
monitoring_btrfs=0

# -------------- Functions Section Start --------------------

echo_debug()
{
    if [ "$debug_mode" -eq 1 ]; then
        echo -e $1
    fi
}

confirm () {
    # call with a prompt string or use a default

    if [ "$should_remove_btrfs" -eq 1 ]; then 
        read -r -p "${1:-Are you sure to remove Btrfs storage? [y/N]} " response
        if [[ $response =~ ^(yes|y)$ ]] 
        then 
                echo 
        else
                exit 1;
        fi         
    fi 
}

create_btrfs() {
    echo "Creating Btrfs for ${1}"

    data_fs=$2
    echo_debug "\tdata_fs=$data_fs"

    mount_folder=$3
    echo_debug "\tmount_folder=$mount_folder"

    btrfs_bs=$4
    echo_debug "\tbtrfs_bs=$btrfs_bs"

    btrfs_count=$5
    echo_debug "\tbtrfs_count=$btrfs_count"

    if [ ! -f "$data_fs" ]; then

        if [ "${6}" = "delete" ]; then
            echo "Deleting $mount_folder folder..." 
            sudo rm -rf $mount_folder
        fi
        if [ "${6}" = "backup" ]; then
            echo "Backuping $mount_folder folder to $mount_folder.backup..." 
            sudo mv $mount_folder $mount_folder.backup
        fi
        if [ "${6}" = "umount" ]; then
            echo "Unmount $mount_folder..."
            sudo umount $mount_folder
        fi

        echo "Creating $mount_folder on Btrfs"
        sudo mkdir -p $mount_folder
        
        echo "Creating device file for Btrfs..."
        sudo dd if=/dev/zero of=$data_fs bs=$btrfs_bs count=$btrfs_count

        echo "Creating partition for Btrfs..."
        sudo mkfs.btrfs -m single $data_fs

        echo "Mounting $mount_folder on Btrfs $data_fs..."
        sudo mount -t btrfs -o loop $data_fs $mount_folder

        echo "Addind write permissions for $mount_folder..."
        sudo chmod 755 $mount_folder

        
        echo "Updating boot loader..."
        sudo su -c "echo '$data_fs        $mount_folder      btrfs        defaults        0        0'   >>  /etc/fstab"        
    else
        echo "Btrfs for ${1} exist! no need to create it."
    fi
}

check_mount() {
    mount_folder=$3

    if [ "${7}" = "exists" ]; then
        mountpoint -q $3 || {
            echo_error "The folder $3 is not mounted." && echo_error "The installation failed" && return 10
        } 
    else
        mountpoint -q $3 && {
            echo_error "The folder $3 is mounted but should not." && echo_error "Run 'sudo lsof $3' to understand reason.' " && echo_error "The process failed" && return 11
        }
    fi

    echo_debug "OK!"
    return 0;
}


remove_btrfs() {
    echo_debug ""

    echo "Removing Btrfs for ${1}"
    
    data_fs=$2
    echo_debug "\tdata_fs=$data_fs"

    mount_folder=$3
    echo_debug "\tmount_folder=$mount_folder"

    btrfs_bs=$4
    echo_debug "\tbtrfs_bs=$btrfs_bs"

    btrfs_count=$5
    echo_debug "\tbtrfs_count=$btrfs_count"

    if [ -f "$data_fs" ]; then
        echo "Unmount $mount_folder..."
        sudo umount $mount_folder

        echo "Deleting $mount_folder and $data_fs..."
        sudo rm $data_fs
        sudo rm -rf $mount_folder
        #sudo mv $mount_folder $mount_folder.backup
    else 
        echo "Cannot remove Btrfs $data_fs (data file does not exist)"
    fi
}

getArray() {
    array=() # Create array
    while IFS= read -r line # Read a line
    do
        if [[ $line == '#'* ]]; then
            continue;
        fi
        if [ -z "$line" ]; then
            continue;
        fi
        array+=("$line") # Append line to the array
    done < "$1"
}

run_condfiguration() {
    configuration=($1)

    echo_debug ""
    echo "Running configurration '${1}' for $2"
    
    data_name=${configuration[0]}
    data_fs=${configuration[1]}
    mount_folder=${configuration[2]}
    btrfs_bs=${configuration[3]}
    btrfs_count=${configuration[4]}
    prev_storage_policy=${configuration[5]}
    
    $2 $data_name $data_fs $mount_folder $btrfs_bs $btrfs_count $prev_storage_policy $3
}

load_configuration()
{
    last_error=0;
    if [ -f "$btrfs_condfiguration_filename" ]; then
        getArray "$btrfs_condfiguration_filename"
        for e in "${array[@]}"
        do
            # echo "$e"
            run_condfiguration "$e" $1 $2
            return_val=$?

            if [ "$return_val" -ne "0" ]; then
                last_error=$return_val;
            fi
        done
    else
        echo "File '$btrfs_condfiguration_filename' does not exist"
    fi

    if [ "$last_error" -ne 0 ]; then
        echo_error "Error occurred during '$1' action running, last error '$last_error'.";
        return $last_error;
    fi
}

echo_error()
{
    echo "$(tput setaf 1) $1 $(tput sgr0)"
}

echo_info()
{
    echo "$(tput setaf 2) $1 $(tput sgr0)"
}

is_supported_kernel_version()
{
    kernel_version=$(awk -F - '{print $1}' <<< "$(uname -r)");
    
    #just in case they are absolutly equal
    if [ $min_kernel_version_for_btrfs = $kernel_version ]; then
        return 0;
    fi

    if [  "$kernel_version" = "`echo -e "$kernel_version\n$min_kernel_version_for_btrfs" | sort -V | head -n1`" ]; then
        # checks that current kernel version is not lower than required, return 1 if not. 
        return 1;
    fi

    return 0;
}

install_fs_for_both()
{
    echo "Creating /data folder..."
    sudo mkdir /data
}

install_btrfs()
{
    echo "Installing Btrfs..."

    sudo apt-get -y --force-yes install btrfs-tools || { echo_error "Installation of Btrfs failed. Try to run manually and then continue."; return 17; }

    # -------------- Creation Section --------------------
    load_configuration create_btrfs || { echo_error "Failed to create Btrfs."; return 18; }

    # -------------- Validation Section --------------------
    load_configuration check_mount "exists" || { echo_error "Failed to mount Btrfs storage."; return 19; }



    echo "Btrfs installation finished successfully."
}

echo_btrfs_partition()
{
    echo_debug ""

    echo_info "Printing Btrfs for ${1}"
    
    data_fs=$2
    echo_debug "\tdata_fs=$data_fs"

    mount_folder=$3
    echo_debug "\tmount_folder=$mount_folder"

    btrfs_bs=$4
    echo_debug "\tbtrfs_bs=$btrfs_bs"

    btrfs_count=$5
    echo_debug "\tbtrfs_count=$btrfs_count"

    sudo btrfs fi df $mount_folder
}

# -------------- Functions Section End --------------------


# -------------- Main Flow Section --------------------

while [[ $1 == -* ]]; do
    case "$1" in
      -h|--help|-\?) show_help; exit 0;;
      -u|--uninstal) uninstal_option=1; shift;;
      -f|--force) force_remove=1; shift;;
      -t|--rbtrfs) should_remove_btrfs=1; shift;;  
      -c|--config_file) btrfs_condfiguration_filename=$2; shift; shift;;    
      -s|--stop) stop_services=1; shift;;
      -m|--mon_btrfs) monitoring_btrfs=1; shift;;
      --) shift; break;;
      -*) echo "invalid option: $1" 1>&2; show_help; exit 1;;
    esac
done

# -------------- Installation / Deletion Btrfs Section --------------------
if [ -z "$btrfs_condfiguration_filename" ] || [ ! -f $btrfs_condfiguration_filename ]; then
    if [ "$monitoring_btrfs" -eq 1 ]; then
        btrfs_condfiguration_filename="/etc/conf_snapper/btrfs.conf"
    else
        echo_error "Wrong configuration file or file '$btrfs_condfiguration_filename' not found!"
        echo
        show_help
        exit 2;
    fi
fi


if [ "$monitoring_btrfs" -eq 1 ]; then
    echo_info "Prints all relevant information about Btrfs storage for $btrfs_condfiguration_filename..."

    echo_info "Show mount..."
    sudo mount | grep btrfs

    echo_info "Show df..."
    sudo df -h | grep loop
    
    echo_info "filesystem show..."
    sudo btrfs fi show
    
    echo_info "filesystem df..."
    load_configuration echo_btrfs_partition

    echo_info "Checks /etc/fstab..."
    more /etc/fstab | grep btrfs

    exit 0;
fi


if [ "$should_remove_btrfs" -eq 1 ]; then
    echo "Stopping confsnapper service if exists..."
    # stopping service if exists
    sudo service confsnapper stop
    echo "Stopped confsnapper service"

    echo "Removing all existing snapshots..." 
    sudo /opt/conf_snapper/curr/src/conf_snapper.py -d
    
    echo "Removing Btrfs..."
    load_configuration remove_btrfs || echo_error "Failed to remove Btrfs according to configuration."

    echo "Cleaning /etc/fstab and creates /etc/fstab.bak file for /etc/fstab..."
    sudo sed -i.bak '/btrfs/d' /etc/fstab

    load_configuration check_mount "dont_exist" || (echo_error "Failed to remove Btrfs according to configuration." && exit 34)

    if [ "$should_exit_after_btrfs_uninstall" -eq 1 ]; then
        exit 0;
    fi
fi


#install_fs_for_both;

# -------------- Btrfs --------------------
is_supported_kernel_version && is_btrfs=1 || echo_error "Current kernel version does not support Btrfs."

if [ "$is_btrfs" -eq 1 ]; then
    install_btrfs || (echo_error "Btrfs installation failed." && exit 1;)
else
    echo "Btrfs installation was not required, use -c option." && exit 1;
fi 

echo ""
echo "You should start all services manually (confsnapper) if they were stopped."


echo_debug "Copy/paste for starting all services:"
echo_debug ""
echo_debug "echo sudo service confsnapper start"

 
