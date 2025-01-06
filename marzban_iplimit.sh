#!/bin/bash
WORKDIR=/usr/local/bin/marzban_iplimit
SERVICE_NAME="marzban-iplimit"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
RED="\033[31m"
GREEN="\033[32m"
YELLOW="\033[33m"
RESET="\033[0m"
FILENAME="marzban_iplimit.bin"

ARCHITECTURE=$(uname -m)
case "$ARCHITECTURE" in
    x86_64)
        ARCHITECTURE="amd64"
        ;;
    aarch64)
        ARCHITECTURE="arm64"
        ;;
    *)
        echo "Unsupported ARCHITECTURE: $ARCHITECTURE"
        echo "Press any key to exit..."
        read -n 1 -s
        exit 1
        ;;
esac

if [ ! -x "$0" ]; then
    echo "Making the script executable..."
    chmod +x "$0"
fi

download_service() {
    local repo="nimaisox/Marzban-iplimit"
    local api_url="https://api.github.com/repos/$repo/releases"
    local download_url
    local filename
    local clean_filename

    if [ -z "$ARCHITECTURE" ]; then
        echo "Error: ARCHITECTURE is not defined. Please set it before running this script."
        return 1
    fi

    if [ ! -d "$WORKDIR" ]; then
        echo "Creating work directory: $WORKDIR"
        mkdir -p "$WORKDIR"
    fi

    echo "Fetching stable releases from GitHub..."
    # Fetch all releases and filter only stable ones
    download_url=$(curl -s "$api_url" | \
        jq -r '.[] | select(.prerelease == false) | .assets[] | select(.name | contains("'"$ARCHITECTURE"'") and contains("linux.bin")) | .browser_download_url' | head -n 1)

    if [ -z "$download_url" ]; then
        echo "Failed to fetch the appropriate release URL for architecture: $ARCHITECTURE. Please check the repository and internet connection."
        return 1
    fi

    filename=$(basename "$download_url")
    echo "Download URL: $download_url"

    echo "Downloading the stable release to $WORKDIR..."
    wget "$download_url" -O "$WORKDIR/$filename"
    if [ $? -eq 0 ]; then
        clean_filename=$(echo "$filename" | sed -E "s/_(${ARCHITECTURE}|linux)//g" | sed 's/\.bin$/.bin/')
        mv "$WORKDIR/$filename" "$WORKDIR/$clean_filename"
        chmod +x "$WORKDIR/$clean_filename"
        echo "The program has been successfully updated to the latest version and is ready to use as $WORKDIR/$clean_filename."
    else
        echo "Failed to download the program. Please check your internet connection or the URL."
        return 1
    fi

    local script_url="https://raw.githubusercontent.com/nimaisox/Marzban-iplimit/master/marzban_iplimit.sh"
    local script_file="$WORKDIR/marzban_iplimit.sh"

    echo "Downloading the script marzban_iplimit.sh..."
    if [ -f "$script_file" ]; then
        echo "Removing old version of $script_file..."
        rm -f "$script_file"
    fi

    if curl -o "$script_file" "$script_url"; then
        chmod +x "$script_file"
        echo "The script $script_file has been successfully updated and is ready to use."
    else
        echo "Failed to download $script_file from $script_url."
        return 1
    fi
}

enable_service() {
    echo "Enable Service..."
    if [ ! -f "$WORKDIR/$FILENAME" ]; then
        echo "Please install the service first."
        echo "Press any key to exit..."
        read -n 1 -s
        return 1
    fi

    echo "Creating systemd service..."
    cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Marzban Iplimit Service
After=network.target
StartLimitIntervalSec=600
StartLimitBurst=5

[Service]
Type=simple
WorkingDirectory=/root/iplimit
ExecStart=/bin/bash $WORKDIR/marzban_iplimit.sh start
ExecStop=/bin/bash $WORKDIR/marzban_iplimit.sh stop
Restart=on-failure
RestartSec=30
TimeoutStopSec=120
KillMode=control-group
User=root
StandardOutput=append:$WORKDIR/service.log
StandardError=append:$WORKDIR/service.log
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME.service"
    echo "Service created and enabled to start at boot."

    sudo ln -sf "$WORKDIR/marzban_iplimit.sh" "/usr/bin/$SERVICE_NAME"
    echo "Command '$SERVICE_NAME' is now available globally."
}

disable_service() {
    echo "Checking if required file exists..."
    
    if [ ! -f "$WORKDIR/$FILENAME" ]; then
        echo "Please install the service first."
        echo "Press any key to exit..."
        read -n 1 -s
        return 1
    fi

    echo "Disabling systemd service..."
    if systemctl is-enabled --quiet "$SERVICE_NAME.service"; then
        sudo systemctl disable "$SERVICE_NAME.service"
        echo "Service $SERVICE_NAME has been disabled."
    else
        echo "AutoStart is not enabled for the service '$SERVICE_NAME'."
        echo "Press any key to exit..."
        read -n 1 -s
        return
    fi
}

install_service() {
    echo "Installing service..."

    if [ -d "$WORKDIR" ]; then
        echo "Service already installed in $WORKDIR."
        echo "Press any key to exit..."
        read -n 1 -s
        return 1
    fi

    sudo mkdir -p "$WORKDIR" || { echo "Failed to create working directory: $WORKDIR"; return 1; }
    sudo chown "$(whoami)":"$(whoami)" "$WORKDIR" || { echo "Failed to set permissions for $WORKDIR"; return 1; }

    cd "$WORKDIR" || { echo "Failed to change to working directory: $WORKDIR"; return 1; }

    if [ ! -f "$FILENAME" ]; then
        echo "$FILENAME not found in $WORKDIR. Attempting to download the latest version..."
        if ! download_service; then
            echo "Failed to download the latest version. Exiting installation."
            return 1
        fi
    fi

    sudo ln -sf "$WORKDIR/marzban_iplimit.sh" "/usr/bin/$SERVICE_NAME"
    echo "Command '$SERVICE_NAME' is now available globally."

    echo "Service installed successfully in $WORKDIR."
}

uninstall_service() {
    echo "Checking if required file exists..."
    if [ ! -f "$WORKDIR/$FILENAME" ]; then
        echo "Please install the service first."
        echo "Press any key to exit..."
        read -n 1 -s
        return
    fi

    echo "Uninstalling the service..."
    if pgrep -f "$WORKDIR/$FILENAME" > /dev/null; then
        echo "Stopping all processes related to $FILENAME..."
        pkill -f "$WORKDIR/$FILENAME"
        sleep 2
        if pgrep -f "$WORKDIR/$FILENAME" > /dev/null; then
            echo "Forcibly killing remaining processes..."
            pkill -9 -f "$WORKDIR/$FILENAME"
        fi
    fi

    if systemctl is-active --quiet "$SERVICE_NAME.service"; then
        echo "Stopping the systemd service..."
        sudo systemctl stop "$SERVICE_NAME.service"
    fi

    if systemctl is-enabled --quiet "$SERVICE_NAME.service"; then
        echo "Disabling the systemd service..."
        sudo systemctl disable "$SERVICE_NAME.service"
    fi

    if [ -n "$WORKDIR" ] && [ -d "$WORKDIR" ]; then
        echo "Removing the working directory: $WORKDIR"
        rm -rf "$WORKDIR"
        echo "Working directory removed successfully."
    else
        echo "Working directory not found or not set: $WORKDIR"
    fi

    if [ -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
        echo "Removing the systemd service file..."
        sudo rm -f "/etc/systemd/system/$SERVICE_NAME.service"
        sudo systemctl daemon-reload
        sudo systemctl reset-failed
        echo "Service file removed and systemd cache cleared."
    else
        echo "Service file not found: /etc/systemd/system/$SERVICE_NAME.service"
    fi

    if [ -f "/usr/bin/$SERVICE_NAME" ]; then
        echo "Removing the executable from /usr/bin..."
        sudo rm -f "/usr/bin/$SERVICE_NAME"
        echo "Executable removed."
    else
        echo "Executable not found: /usr/bin/$SERVICE_NAME"
    fi

    if [ -d "/var/log/$SERVICE_NAME" ]; then
        echo "Removing logs..."
        sudo rm -rf "/var/log/$SERVICE_NAME"
        echo "Logs removed."
    fi

    if ! pgrep -f "$WORKDIR/$FILENAME" > /dev/null; then
        echo "Service has been successfully stopped and uninstalled."
    else
        echo "Warning: Some processes might still be running."
    fi
}


start_service() {
    echo "Starting service..."

    if [ ! -f "$WORKDIR/$FILENAME" ]; then
        echo "Please install the service first."
        echo "Press any key to exit..."
        read -n 1 -s
        return 1
    fi

    config_file="$WORKDIR/config.json"
    if [ ! -f "$config_file" ]; then
        echo "Error: Configuration file 'config.json' does not exist in the working directory."
        echo "Press any key to exit..."
        read -n 1 -s
        return 1
    fi

    pushd "$WORKDIR" > /dev/null || {
        echo "Failed to change directory to '$WORKDIR'."
        echo "Press any key to exit..."
        read -n 1 -s
        return 1
    }

    if pgrep -f "$FILENAME" > /dev/null; then
        echo "Service '$FILENAME' is already running."
        echo "Press any key to exit..."
        read -n 1 -s
        return 1
    fi

    echo "Starting service '$FILENAME'..."
    nohup "./$FILENAME" >"$WORKDIR/service.log" 2>&1 &
    sleep 2

    if pgrep -f "$FILENAME" > /dev/null; then
        echo "Service '$FILENAME' started successfully."
    else
        echo "Failed to start service '$FILENAME'. Please check the logs or troubleshoot manually."
        echo "Press any key to exit..."
        read -n 1 -s
        return 1
    fi

    popd > /dev/null
}

stop_service() {
    echo "Stopping services..."
    if ! pgrep -f "$FILENAME" > /dev/null; then
        echo "No running marzban Iplimit service. Nothing to stop."
        echo "Press any key to exit..."
        read -n 1 -s
        return 0
    fi

    if pgrep -f "$FILENAME" > /dev/null; then
        echo "Stopping $FILENAME process..."
        pkill -f "$FILENAME"
        sleep 1

        if pgrep -f "$FILENAME" > /dev/null; then
            echo "Failed to stop marzban iplimit service. Please try manually."
            exit 1
        else
            echo "marzban iplimit service stopped successfully."
        fi
    else
        echo "No running $FILENAME process found."
    fi

    if [ -d "$WORKDIR" ]; then
        echo "Cleaning up log files..."
        rm -f "$WORKDIR/app.log" "$WORKDIR/service.log"
        echo "Log files removed."
    else
        echo "Working directory not found: $WORKDIR"
    fi

    echo "Services stopped successfully."
}

logs_service() {
    local app_log="$WORKDIR/app.log"
    local service_log="$WORKDIR/service.log"

    while true; do
        clear
        echo "╔══════════════════════════════════════════════════╗"
        echo "║               Select a Log to View               ║"
        echo "╠══════════════════════════════════════════════════╣"
        echo "║ 1) View app.log                                  ║"
        echo "║ 2) View service.log                              ║"
        echo "║ 3) Back to Menu                                  ║"
        echo "╚══════════════════════════════════════════════════╝"
        echo ""

        read -p "Please select an option [1-3]: " log_choice

        case $log_choice in
            1)
                if [ -f "$app_log" ]; then
                    echo "Displaying real-time updates of app.log (Press Ctrl+C to exit):"
                    tail -f "$app_log"
                else
                    echo "Server is stopped (Log file not found: $app_log)"
                    echo "Press any key to return..."
                    read -n 1 -s
                fi
                ;;
            2)
                if [ -f "$service_log" ]; then
                    echo "Displaying real-time updates of service.log (Press Ctrl+C to exit):"
                    tail -f "$service_log"
                else
                    echo "Autostart is not active (Log file not found: $service_log)"
                    echo "Press any key to return..."
                    read -n 1 -s
                fi
                ;;
            3)
                echo "Returning to the menu."
                break
                ;;
            *)
                echo "Invalid choice. Please select 1, 2, or 3."
                echo "Press any key to return..."
                read -n 1 -s
                ;;
        esac
    done
}

config_service() {
    local valid_bot_token_regex="^[0-9]{9,10}:[a-zA-Z0-9_-]{35,}$"
    local valid_admin_regex="^[0-9]+$"
    local valid_proxy_regex="^(http|socks5)://(([a-zA-Z0-9._~-]+:[a-zA-Z0-9._~-]+@)?([a-zA-Z0-9._~-]+|\d{1,3}(\.\d{1,3}){3}):\d{2,5})$"

    if [ ! -f "$WORKDIR/config.json" ]; then
        mkdir -p "$WORKDIR"
        cat > "$WORKDIR/config.json" <<EOL
{
  "BOT_TOKEN": "",
  "ADMINS": [],
  "PROXY_FOR_API": ""
}
EOL
        if [ -f "$WORKDIR/config.json" ]; then
            echo "Configuration file not found, created successfully."
        else
            echo "Error: Failed to create configuration file."
            echo "Press any key to exit..."
            read -n 1 -s
            return 1
        fi
    fi

    local field
    local value
    local confirm
    local config_file="$WORKDIR/config.json"
    while true; do
        echo "Choose an option:"
        echo "1. Set or Update BOT_TOKEN"
        echo "2. Set or Update ADMINS"
        echo -e "3. Set or Update PROXY_FOR_API ${YELLOW}(Optional)${RESET}"
        echo "Enter the corresponding number (or leave it blank to exit):"
        read -p "> " field

        if [[ -z "$field" ]]; then
            echo "Exiting configuration menu..."
            break
        fi

        case "$field" in
            1)
                value=$(jq -r '.BOT_TOKEN' "$config_file" 2>/dev/null || echo "")
                if [ -z "$value" ]; then
                    echo "No BOT_TOKEN is currently set."
                else
                    echo "Current BOT_TOKEN is: $value"
                    read -p "Do you want to change it? (y/n) (or leave it blank to stop): " confirm
                    if [[ -z "$confirm" || $confirm != [Yy]* ]]; then
                        continue
                    fi
                fi

                echo "You must create a bot and get the token, you can get it from @BotFather in Telegram."
                while true; do
                    read -p "Enter new BOT_TOKEN (or leave it blank to stop): " value
                    if [[ -z "$value" ]]; then
                        echo "Operation canceled. Returning to menu..."
                        break
                    elif [[ $value =~ $valid_bot_token_regex ]]; then
                        jq --arg token "$value" '.BOT_TOKEN = $token' "$config_file" > tmp.json && mv tmp.json "$config_file"
                        echo "The BOT_TOKEN has been updated."
                        break
                    else
                        echo "Invalid BOT_TOKEN format. Please try again."
                    fi
                done
                ;;

            2)
                value=$(jq -r '.ADMINS[]' "$config_file" 2>/dev/null || echo "[]")
                if [ -z "$value" ]; then
                    echo "No ADMINS are currently set."
                else
                    echo "Current ADMINS are: $value"
                    read -p "Do you want to change them? (y/n) (or leave it blank to stop): " confirm
                    if [[ -z "$confirm" || $confirm != [Yy]* ]]; then
                        continue
                    fi
                fi

                echo "You must set your chat ID, you can get it from @userinfobot in Telegram."
                admins=()
                while true; do
                    read -p "Enter new ADMIN ID (or leave it blank to stop): " value
                    if [[ -z "$value" ]]; then
                        if [ ${#admins[@]} -eq 0 ]; then
                            echo "No ADMIN set. At least one ADMIN must be entered."
                        else
                            echo "Admins have been set. Saving changes..."
                            jq --argjson admin "$(printf '%s\n' "${admins[@]}" | jq -R . | jq -s .)" '.ADMINS = $admin' "$config_file" > tmp.json && mv tmp.json "$config_file"
                            echo "The ADMINS have been updated."
                            break
                        fi
                    elif [[ "$value" =~ $valid_admin_regex ]]; then
                        admins+=("$value")
                        echo "Added ADMIN ID: $value"
                    else
                        echo "Invalid ADMIN ID. Must be a numeric value. Please try again."
                    fi
                done
                ;;

            3)
                value=$(jq -r '.PROXY_FOR_API' "$config_file" 2>/dev/null || echo "")
                if [ -z "$value" ]; then
                    echo "No PROXY_FOR_API is currently set."
                else
                    echo "Current PROXY_FOR_API is: $value"
                    read -p "Do you want to change it? (y/n) (or leave it blank to stop): " confirm
                    if [[ -z "$confirm" || $confirm != [Yy]* ]]; then
                        continue
                    fi
                fi

                echo -e "${YELLOW}Enter the proxy in the format http://username:password@ip:port or socks5://username:password@ip:port (Optional - leave it blank if not needed):${RESET}"
                while true; do
                    read -p "Enter new PROXY_FOR_API (or leave it blank to stop): " value
                    if [[ -z "$value" ]]; then
                        echo "Operation canceled. Returning to menu..."
                        break
                    elif [[ "$value" =~ $valid_proxy_regex ]]; then
                        jq --arg proxy "$value" '.PROXY_FOR_API = $proxy' "$config_file" > tmp.json && mv tmp.json "$config_file"
                        echo "The PROXY_FOR_API has been updated."
                        break
                    else
                        echo "Invalid proxy format. Please try again."
                    fi
                done
                ;;

            *)
                echo "Invalid option. Please enter a valid number (1, 2, or 3)."
                ;;
        esac
    done

    [ -f tmp.json ] && rm -f tmp.json
}

ACTION=$1

if [[ -n "$ACTION" ]]; then
    case $ACTION in
        start)
            echo "Starting the marzban iplimit service..."
            start_service
            exit 0
            ;;
        stop)
            echo "Stopping the marzban iplimit service..."
            stop_service
            exit 0
            ;;
        restart)
            echo "Restarting the marzban iplimit service..."
            if pgrep -f "$FILENAME" > /dev/null; then
                stop_service
                start_service    
            else
                echo "Service not running."
                echo "Press any key to exit..."
                read -n 1 -s
                return 1                
            fi
            exit 0
            ;;
        install)
            echo "Installing the marzban iplimit service..."
            install_service
            exit 0
            ;;
        uninstall)
            echo "Uninstalling the marzban iplimit service..."
            uninstall_service
            exit 0
            ;;
        enable)
            echo "Enabling autostart for the marzban iplimit service..."
            enable_service
            exit 0
            ;;
        disable)
            echo "Disabling autostart for the marzban iplimit service..."
            disable_service
            exit 0
            ;;
        config)
            echo "Opening the configuration for the marzban iplimit service..."
            config_service
            exit 0
            ;;
        update)
            echo "Updating the configuration for the marzban iplimit service..."

            if [ ! -f "$WORKDIR/$FILENAME" ]; then
                echo "Please install the service first."
                echo "Press any key to exit..."
                read -n 1 -s
                return 1
            fi

            WAS_RUNNING=false
            if pgrep -f "$FILENAME" > /dev/null; then
                WAS_RUNNING=true
                echo "Stopping $FILENAME process..."
                pkill -f "$FILENAME"
                sleep 1

                if pgrep -f "$FILENAME" > /dev/null; then
                    echo "Failed to stop marzban iplimit service. Please try manually."
                    exit 1
                else
                    echo "marzban iplimit service stopped successfully."
                fi
            else
                echo "No running $FILENAME process found."
            fi

            download_service

            if [ "$WAS_RUNNING" = true ]; then
                echo "Starting service '$FILENAME'..."
                nohup "./$FILENAME" >"$WORKDIR/service.log" 2>&1 &
                sleep 2

                if pgrep -f "$FILENAME" > /dev/null; then
                    echo "Service '$FILENAME' started successfully."
                else
                    echo "Failed to start service '$FILENAME'. Please check the logs or troubleshoot manually."
                    echo "Press any key to exit..."
                    read -n 1 -s
                    return 1
                fi
            else
                echo "Service was not running before update. No need to restart."
            fi

            exit 0
            ;;
        *)
            echo "Invalid action. Usage: $0 {start|stop|restart|install|uninstall|enable|disable|config|update}"
            exit 1
            ;;
    esac
fi

status_service() {
    APP_STATE="Stopped"
    AUTOSTART_STATE="No"
    INSTALL_STATE="Not Install"

    if pgrep -f "$FILENAME" > /dev/null; then
        APP_STATE="${GREEN}Running${RESET}"
    else
        APP_STATE="${RED}Stopped${RESET}"
    fi

    if systemctl is-enabled --quiet "$SERVICE_NAME.service" 2>/dev/null; then
        AUTOSTART_STATE="${GREEN}Enabled${RESET}"
    else
        AUTOSTART_STATE="${RED}Disabled${RESET}"
    fi

    if [ -f "$WORKDIR/$FILENAME" ]; then
        INSTALL_STATE="${GREEN}Installed${RESET}"
    else
        INSTALL_STATE="${RED}Not Installed${RESET}"
    fi

    echo -e "App Status: $APP_STATE"
    echo -e "AutoStart Status: $AUTOSTART_STATE"
    echo -e "Install Status: $INSTALL_STATE"
}

EXIT_PROGRAM=false

main_menu() {
    clear
    echo "╔════════════════════════════════════════════════╗"
    echo "║         Manage Marzban Iplimit Service         ║"
    echo "╠════════════════════════════════════════════════╣"
    echo "║ 1) Install                                     ║"
    echo "║ 2) Enable AutoStart                            ║"
    echo "║ 3) Disable AutoStart                           ║"
    echo "║ 4) Start                                       ║"
    echo "║ 5) Stop                                        ║"
    echo "║ 6) Restart                                     ║"
    echo "║ 7) View Logs                                   ║"
    echo "║ 8) Update                                      ║"
    echo "║ 9) Uninstall                                   ║"
    echo "║ 10) Configuration                              ║"
    echo "╠════════════════════════════════════════════════╣"
    echo "║ GitHub Repository:                             ║"
    echo "║ https://github.com/nimaisox/Marzban-iplimit    ║"
    echo "╚════════════════════════════════════════════════╝"
    echo ""
    status_service
    echo ""
    read -p "Please enter your selection [1-10] (Leave empty to exit): " choice

    if [[ -z "$choice" ]]; then
        echo "Exiting. Goodbye!"
        EXIT_PROGRAM=true
        return
    fi

    case $choice in
        1)
            install_service
            status_service
            ;;
        2)
            enable_service
            status_service
            ;;
        3)
            disable_service
            status_service
            ;;
        4)
            start_service
            status_service
            ;;
        5)
            stop_service
            status_service
            ;;
        6)
            if pgrep -f "$FILENAME" > /dev/null; then
                stop_service
                start_service    
            else
                echo "Service not running."
                echo "Press any key to exit..."
                read -n 1 -s
                return 1                
            fi
            ;;
        7)
            logs_service
            ;;
        8)
            echo "Updating the configuration for the marzban iplimit service..."

            if [ ! -f "$WORKDIR/$FILENAME" ]; then
                echo "Please install the service first."
                echo "Press any key to exit..."
                read -n 1 -s
                return 1
            fi

            WAS_RUNNING=false
            if pgrep -f "$FILENAME" > /dev/null; then
                WAS_RUNNING=true
                echo "Stopping $FILENAME process..."
                pkill -f "$FILENAME"
                sleep 1

                if pgrep -f "$FILENAME" > /dev/null; then
                    echo "Failed to stop marzban iplimit service. Please try manually."
                    exit 1
                else
                    echo "marzban iplimit service stopped successfully."
                fi
            else
                echo "No running $FILENAME process found."
            fi

            download_service

            if [ "$WAS_RUNNING" = true ]; then
                echo "Starting service '$FILENAME'..."
                nohup "./$FILENAME" >"$WORKDIR/service.log" 2>&1 &
                sleep 2

                if pgrep -f "$FILENAME" > /dev/null; then
                    echo "Service '$FILENAME' started successfully."
                else
                    echo "Failed to start service '$FILENAME'. Please check the logs or troubleshoot manually."
                    echo "Press any key to exit..."
                    read -n 1 -s
                    return 1
                fi
            else
                echo "Service was not running before update. No need to restart."
            fi

            status_service
            ;;
        9)
            uninstall_service
            status_service
            ;;
        10)
            config_service
            ;;
        0)
            echo "Exiting. Goodbye!"
            EXIT_PROGRAM=true 
            ;;
        *)
            echo -e "${RED}Invalid choice. Please enter a number between 1 and 11.${RESET}"
            echo "Press any key to exit..."
            read -n 1 -s
            ;;
    esac
}

while ! $EXIT_PROGRAM; do
    main_menu
done
