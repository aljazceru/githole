from flask import Flask, jsonify, request
import docker
import socket
import subprocess
import sqlite3
import os
import time
from datetime import datetime, timedelta
from nostr_sdk import Client, NostrSigner, Keys, PublicKey, Event, UnsignedEvent, EventBuilder, Filter, HandleNotification, Timestamp, nip04_decrypt, nip59_extract_rumor, SecretKey, init_logger, LogLevel
from settings import *
from docker import APIClient

init_logger(LogLevel.INFO)
os.makedirs('/var/lib/ghole', exist_ok=True)

app = Flask(__name__)
client = docker.from_env()
DB_PATH = '/var/lib/ghole/database.db'

sk = SecretKey.from_hex(NOSTR_KEY)
keys = Keys(sk)
sk = keys.secret_key()
pk = keys.public_key()



def ensure_directory_exists(path):
    os.makedirs(path, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    ensure_directory_exists('/var/lib/ghole')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS containers (
        user_npub TEXT NOT NULL,
        container_id TEXT NOT NULL,
        container_port INTEGER NOT NULL,
        volume_path TEXT,
        repo_name TEXT NOT NULL,
        notification_success INTEGER NULL DEFAULT 0,
        PRIMARY KEY (container_id)
    )
    ''')
    conn.commit()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_notifications (
        repo_name TEXT,
        user_npub TEXT,
        message TEXT,
        status TEXT,
        PRIMARY KEY (repo_name, user_npub)
    )
    ''')
    conn.commit()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS subscriptions (
        user_npub TEXT,
        repo_name TEXT,
        expiration_date DATETIME,
        PRIMARY KEY (user_npub, repo_name)
    )
    ''')
    conn.commit()
    conn.close()

# add a new subscription upon container creation
def add_subscription(user_npub, repo_name):
    expiration_date = datetime.utcnow() + timedelta(days=SUBSCRIPTION_LENGTH_DAYS)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO subscriptions (user_npub, repo_name, expiration_date) VALUES (?, ?, ?)
    ''', (user_npub, repo_name, expiration_date))
    conn.commit()
    conn.close()

# get subscriptions that expire in 3 days
def get_subscriptions_to_expire():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT user_npub, repo_name, expiration_date FROM subscriptions WHERE expiration_date < ?
    ''', (datetime.utcnow() + timedelta(days=3),))
    subscriptions = cursor.fetchall()
    conn.close()
    return subscriptions

# notify users that their subscription is about to expire
def notify_users_of_subscription_expiration():
    subscriptions = get_subscriptions_to_expire()
    for user_npub, repo_name, expiration_date in subscriptions:
        message = f'Your subscription to {repo_name} is about to expire on {expiration_date}. Go to https://nostrocket.org/products to renew your subscription.'
        send_user_notification(user_npub, message)


# Function to save notification
def save_notification(repo_name, user_npub, message, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO user_notifications (repo_name, user_npub, message, status) VALUES (?, ?, ?, ?)
    ''', (repo_name, user_npub, message, status))
    conn.commit()
    conn.close()

# Function to retry unsuccessful notifications
def retry_unsuccessful_notifications():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT repo_name, user_npub, message FROM user_notifications WHERE status = 'unsuccessful'
    ''')
    unsuccessful_notifications = cursor.fetchall()
    conn.close()

    for repo_name, user_npub, message in unsuccessful_notifications:
        # Implement retry logic here. Upon success:
        update_notification_status(repo_name, user_npub, 'successful')

def update_notification_status(repo_name, user_npub, new_status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE user_notifications SET status = ? WHERE repo_name = ? AND user_npub = ?
    ''', (new_status, repo_name, user_npub))
    conn.commit()
    conn.close()

# get list of containers with names and ports
def get_containers():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT container_id, container_port, volume_path, repo_name FROM containers
    ''')
    containers = cursor.fetchall()
    conn.close()
    return containers

def find_available_port(start=8000, end=18999):
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            result = sock.connect_ex(('localhost', port))
            if result != 0:
                return port
    raise Exception("No available port found.")

def update_nginx_config(repo_name, container_port):
    config_snippet = f"""
    location /{repo_name}/ {{
        proxy_pass http://localhost:{container_port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
    """
    
    # check if the path exists
    if not os.path.exists(f'/etc/nginx/dynamic_routes/{repo_name}.conf'):
        config_path = f'/etc/nginx/dynamic_routes/{repo_name}.conf'
        with open(config_path, 'w') as file:
            file.write(config_snippet)
        subprocess.run(['nginx', '-s', 'reload'], check=True)

def register_container_in_db(user_npub, container_id, port, volume_path, repo_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO containers (user_npub, container_id, container_port, volume_path, repo_name) VALUES (?, ?, ?, ?, ?)',
                   (user_npub, container_id, port, volume_path, repo_name))
    conn.commit()
    conn.close()
    

def parse_repo_name(url):
    # remove .git if it exists
    if url.endswith('.git'):
        url = url[:-4]
    return url.split('/')[-1]


def send_user_notification(user_npub,message):
    sk = SecretKey.from_hex(NOSTR_KEY)
    keys = Keys(sk)
    sk = keys.secret_key()
    pk = keys.public_key()
    destination = PublicKey().from_bech32(user_npub)
    signer = NostrSigner.keys(keys)
    client = Client(signer)
    client.add_relays(RELAY_LIST)
    client.connect()
    event = EventBuilder.encrypted_direct_msg(keys, PublicKey().from_bech32(user_npub), message,None).to_event(keys)
    print(event.as_json())
    try:
        client.send_event(event)
        client.disconnect()
        return True
    except Exception as e:
        print(e)
        client.disconnect()
        return False


# add endpoint to return all containers
@app.route('/get_all_containers', methods=['GET'])
def get_all_containers():
    containers = get_containers()
    return jsonify({'containers': containers})




# Check if a repo name is available
@app.route('/check_name', methods=['GET'])
def check_name():
    repo_name = request.args.get('repo_name')
    if not repo_name:
        return jsonify({'error': 'Missing repo_name parameter'}), 400

    # Check in database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT EXISTS(SELECT 1 FROM containers WHERE repo_name=?)", (repo_name,))
    exists_in_db = cursor.fetchone()[0]

    # Check in reserved names file
    with open('/var/lib/ghole/reserved_names.txt', 'r') as file:
        reserved_names = file.read().splitlines()
    exists_in_file = repo_name in reserved_names

    conn.close()

    # If the name does not exist in the database and the file, it's considered free
    if not exists_in_db and not exists_in_file:
        return jsonify({'message': 'Name is free'}), 200  # Name is free
    else:
        return jsonify({'message': 'Name is taken'}), 406  # Name is taken

# Deploy new container for a repo
@app.route('/deploy', methods=['POST'])
def deploy():
    data = request.json
    user_npub = data['user_npub']
    repo_name = data['repo_name']
    # if repo_name starts with 'http' or 'https', it's a URL
    if repo_name.startswith('http'):
        volume_name = parse_repo_name(repo_name)
    else:
        volume_name = repo_name
        
    # query the database if the repo_name was already deployed
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM containers WHERE repo_name = ?', (volume_name,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return jsonify({"status": "error", "message": "Repo name is already taken"})

    # volume path
    volume_path = f"/srv/user_data/{volume_name}/"  # Updated volume path
    image_name = 'ghole'
    
    ensure_directory_exists(volume_path)
    # Find an available port
    available_port = find_available_port()

    # env
    environment = {'REPO_NAME': repo_name, 'USER_NPUB': user_npub}

    # Specify volume binding
    volumes = {volume_path: {'bind': '/srv/repos/', 'mode': 'rw'}}

    # Deploy the container with the specified volume
    container = client.containers.run(
        image_name,
        detach=True,
        name=volume_name,  # Set the container name to repo_name
        ports={'80/tcp': available_port},
        volumes=volumes,
        environment=environment,
        restart_policy={"Name": "unless-stopped"}  # Container restart policy
    ) 
    update_nginx_config(volume_name, available_port)
    register_container_in_db(user_npub, container.id, available_port, volume_path, volume_name)
    add_subscription(user_npub, volume_name)
    
    return jsonify({"status": "success", "message": "Container deployed and route configured, volume created"})

# create and endpoint that prepares a gzipped export of container with its data
@app.route('/export', methods=['POST'])
def export():
    data = request.json
    repo_name = data['repo_name']
    volume_name = repo_name
    export_path = f"/srv/exports/{volume_name}.tar.gz"
    try:
        container = client.containers.get(volume_name)
        client.api.export(container, export_path)
        return jsonify({"status": "success", "message": "Exported successfully", "export_path": export_path})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to export: {str(e)}"}), 500

# create endpoint that accepts notifications from client
@app.route('/user_notification', methods=['POST'])
def user_notification():
    data = request.json
    pear_key = data['pear_key']
    pear_repo = data['pear_repo']
    pear_seed = data['pear_seed']
    repo_name = data['repo_name']
    user_npub = data['user_npub']
    

    
    msg = f"Your repo {repo_name} has been deployed.\n Here is all the information you need to access it:\n\n Http access:\nhttps://ghole.xyz/{repo_name}\n Pear key: {pear_key}\nPear repo: {pear_repo}\nPear seed: {pear_seed}\nRepo name: {repo_name}"
    try: 
        send_user_notification(user_npub, msg)
        return jsonify({"status": "success"})
    except Exception as e:
        print(e)
        return jsonify({"status": "error"})

# Run the app
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=31337, debug=True)
