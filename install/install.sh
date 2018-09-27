#!/usr/bin/env bash
###################################################################
####	Installation / Upgrade conf_snapper				  	   ####
###################################################################

SNAPPER_CONF_FOLDER=/etc/conf_snapper
DEFAULT_SNAPPER_CONFIGURATION_FILE=$SNAPPER_CONF_FOLDER/snapper_conf.json
SNAPPER_LOG_FOLDER=/var/log/conf_snapper
dir=$(basename $(pwd))

sudo apt-get -y install python-pip
sudo pip install apscheduler==3.3.1
# Install for python 2.7.3
sudo pip install funcsigs==1.0.2
sudo pip install futures==3.0.5

echo "Creating local configuration and folders..."
if [ ! -d "$SNAPPER_LOG_FOLDER" ]; then
    echo "$SNAPPER_LOG_FOLDER dooesn't exist, creating."
    mkdir $SNAPPER_LOG_FOLDER
fi

if [ ! -d "$SNAPPER_CONF_FOLDER" ]; then
    echo "$SNAPPER_CONF_FOLDER dooesn't exist, creating."
    mkdir $SNAPPER_CONF_FOLDER
fi

if [ -f "$DEFAULT_SNAPPER_CONFIGURATION_FILE" ]
then
	echo "$DEFAULT_SNAPPER_CONFIGURATION_FILE already exist."
else
	echo "$DEFAULT_SNAPPER_CONFIGURATION_FILE does't exist, creating default."
	cp /opt/conf_snapper/$dir/conf/snapper_conf.json $DEFAULT_SNAPPER_CONFIGURATION_FILE
fi
echo "Creating local configuration and folders - DONE"

echo "Removing updater cron..."
# remove updater cron if exists
rm -f /etc/cron.d/confsnapper
echo "Removed updater cron"

echo "Stopping confsnapper service if exists..."
# stopping service if exists
service confsnapper stop
echo "Stopped confsnapper service"

echo "Installing confsnapper service..."
# Install updater service
ln -s /opt/conf_snapper/curr/service/confsnapper /etc/init.d/confsnapper
echo "Installed confsnapper service"

echo "Installing confsnapper service watchdog..."
# Install confsnapper watchdog
cat > /etc/cron.d/monitor_confsnapper <<'EOF'  
MAILTO=""
* * * * * root /opt/conf_snapper/curr/scripts/service_watcher.sh confsnapper >> /var/log/conf_snapper/monitor_confsnapper.log 2>&1

EOF
echo "Watchdog installed."

echo "conf_snapper installed in $dir, linking curr directory."
rm -f /opt/conf_snapper/curr
ln -fs /opt/conf_snapper/${dir}/ /opt/conf_snapper/curr
update-rc.d confsnapper defaults

echo "Starting confsnapper service..."
service confsnapper start
 

