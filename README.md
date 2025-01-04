# Marzban-iplimit

**Limiting the number of active users with IP for [Marzban](https://github.com/Gozargah/Marzban)**  
*(with xray logs)*  
Supports both IPv4 and IPv6 And Marzban-node  
*(Tested on Ubuntu 22.04 & 24.04)*

<hr>

## Table of Contents

- [Installation](#installation)
- [Telegram Bot Commands](#telegram-bot-commands)
- [Common Issues and Solutions](#common-issues-and-solutions)
- [Build](#build)

## Installation

You can install Marzban-iplimit by running the following command in your terminal:

```bash
bash <(curl -sSL https://raw.githubusercontent.com/nimaisox/Marzban-iplimit/master/marzban-iplimit.sh)
```

After running the command, you will see a menu with the following options:

```
-----------------------------
1. Start the script
2. Stop the script
3. Attach to the script
4. Update the script
5. Create or Update telegram BOT_TOKEN
6. Create or Update ADMINS
7. Exit
-----------------------------
Enter your choice:
```

![Loading Gif](docs/1.gif)

And after that you need input your panel information and other settings:

![Loading Gif](docs/1.png)

After that script runs automatically and you can see the logs.

## Telegram Bot Commands

Marzban-iplimit can be controlled via a Telegram bot. Here are the available commands:

- `/start`: Start the bot.
- `/create_config`: Configure panel information (username, password, etc.).
- `/set_special_limit`: Set a specific IP limit for each user (e.g., test_user limit: 5 ips).
- `/show_special_limit`: Show the list of special IP limits.
- `/add_admin`: Give access to another chat ID and create a new admin for the bot.
- `/admins_list`: Show the list of active bot admins.
- `/remove_admin`: Remove an admin's access to the bot.
- `/country_code`: Set your country. Only IPs related to that country are counted (to increase accuracy).
- `/set_except_user`: Add a user to the exception list.
- `/remove_except_user`: Remove a user from the exception list.
- `/show_except_users`: Show the list of users in the exception list.
- `/set_general_limit_number`: Set the general limit number. If a user is not in the special limit list, this is their limit number.
- `/set_check_interval`: Set the check interval time.
- `/set_time_to_active_users`: Set the time to active users.
- `/backup`: Send the 'config.json' file.

## Common Issues and Solutions

1.  **Uninstalling Marzban-iplimit Script**

    - How can I uninstall the Marzban-iplimit script?
    - Simply Stop the script and then delete the script folder.

2.  **Connections Persisting After Disabling**

    - Users remain connected even after disabling. Why?
    - This issue is related to the xray core. Connections persist until the user manually closes them. So you have to wait a little until all the connections are closed

3.  **Restarting After Changing JSON Config File**

    - Is a restart needed after modifying the JSON config file?
    - No, a restart isn't necessary. The program adapts to changes in the JSON file in short time.

4.  **Running Script on Different VPS**

    - Can I run the script on a different VPS?
    - Absolutely, the script is flexible and works seamlessly on any VPS or even on your local machine.

5.  **Tunneling and User IP Detection**

    - Tunneling returns the tunnel server IP for users. Any solutions?
    - Tunneling poses challenges. For better IP detection, consider alternative methods 

6.  **I'm using haproxy why I don't have logs**

    - You need to add this to your haproxy config file:
      `option forwardfor`
      And then restart your haproxy service.

7.  **I'm not using tunnel or haproxy or anything else but still I don't have logs**

    - you need add this to your xray config file(If it doesn't exist) :
      ```json
      "log": {
          "loglevel": "info"
      },
      ```

If you still have a problem you can open an issue on the [issues page](https://github.com/nimaisox/Marzban-iplimit/issues)<br>

## Build

Marzban-iplimit provides pre-built versions for Windows and Linux (both amd64 and arm64) which can be found on the [releases page](https://github.com/nimaisox/Marzban-iplimit/releases).

The Windows_amd64 and Linux_amd64 builds are created using GitHub Actions. You can check the build details on the [actions page](https://github.com/nimaisox/Marzban-iplimit/actions/).

The Linux_arm64 build is created on a local machine due to GitHub's lack of ARM machines and the build method's lack of support for Cross Compiling. However, you can build it on your own machine, or use GitHub Actions to build it on your own.<br>
If you want to build Marzban-iplimit yourself, you'll first need to install the build essentials, which includes gcc, g++, and more. You can do this with the following command:

```bash
sudo apt install build-essential
```

Next, install the necessary dependencies:<br>
`pip install -r build_requirements.txt`<br>
And at the end you build it with [nuitka](https://nuitka.net/)<br>

```bash
python3 -m nuitka --standalone --onefile --follow-imports --include-plugin-directory=utils --include-package=websockets,logging --python-flag="-OO" main.py
```

### Running Without Building

You can also use this program without building it. Just install the dependencies and run it normally:

```bash
git clone https://github.com/nimaisox/Marzban-iplimit.git
cd Marzban-iplimit
pip install -r requirements.txt
python3 main.py
```

<hr>

## Credits
This project is based on the original work by [Houshmand](https://github.com/houshmand-2005).
