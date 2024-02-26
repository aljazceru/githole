import logging
from flask import Flask, request, jsonify
import base64
import subprocess

# Set up logging
logging.basicConfig(filename='/var/log/app.log', level=logging.INFO)

app = Flask(__name__)

@app.route('/auth', methods=['POST'])
def auth():
    # Decode the Base64 payload from the request
    auth_header = request.headers.get('Authorization').split(' ')[1]
    logging.info(f'Auth header: {auth_header}')
    # Add padding if necessary
    missing_padding = len(auth_header) % 4
    if missing_padding:
        auth_header += '='* (4 - missing_padding)
    auth_payload = base64.b64decode(auth_header).decode()
    logging.info(f'Auth payload: {auth_payload}')
    # Execute the bash script with the decoded payload as an argument
    result = subprocess.run(['bash', 'check.sh', auth_payload], capture_output=True, text=True)
    output = result.stdout.strip()
    logging.info(f'Script output: {output}')
    
    # Return appropriate status code based on the script's output
    if output == "PASS":
        return jsonify({"message": "Authentication successful"}), 200
    elif output == "FAIL":
        return jsonify({"message": "Authentication failed"}), 403
    else:
        # Handle unexpected output
        logging.error('Unexpected output')
        return jsonify({"message": "Error processing request"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1337,debug=True)
