from flask import Flask, request, jsonify
import base64
import subprocess

# this is an ugly hack for demo purposes

app = Flask(__name__)

@app.route('/auth', methods=['POST'])
def auth():
    # Decode the Base64 payload from the request
    auth_header = request.headers.get('Authorization').split(' ')[1]
    print(auth_header)
    # Add padding if necessary
    missing_padding = len(auth_header) % 4
    if missing_padding:
        auth_header += '='* (4 - missing_padding)
    auth_payload = base64.b64decode(auth_header).decode()
    print(auth_payload)
    # Execute the bash script with the decoded payload as an argument
    result = subprocess.run(['bash', 'check.sh', auth_payload], capture_output=True, text=True)
    output = result.stdout.strip()
    
    # Return appropriate status code based on the script's output
    if output == "PASS":
        return jsonify({"message": "Authentication successful"}), 200
    elif output == "FAIL":
        return jsonify({"message": "Authentication failed"}), 403
    else:
        # Handle unexpected output
        return jsonify({"message": "Error processing request"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1337)
