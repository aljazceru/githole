from flask import Flask, jsonify, request
import docker
import socket
import subprocess
import sqlite3
import os

os.makedirs('/var/lib/ghole', exist_ok=True)

app = Flask(__name__)
client = docker.from_env()
DB_PATH = '/var/lib/ghole/database.db'

def ensure_directory_exists(path):
    os.makedirs(path, exist_ok=True)


def init_db():
    ensure_directory_exists('/var/lib/ghole')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS containers (
        user_npub TEXT NOT NULL,
        container_id TEXT NOT NULL,
        container_port INTEGER NOT NULL,
        volume_path TEXT,
        repo_name TEXT NOT NULL,
        PRIMARY KEY (container_id)
    )
    ''')
    conn.commit()
    conn.close()

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
    conn = sqlite3.connect(DB_PATH)
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

# POST /deploy


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
    
    return jsonify({"status": "success", "message": "Container deployed and route configured, volume created"})


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=31337, debug=True)
