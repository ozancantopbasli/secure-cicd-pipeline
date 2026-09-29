from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    return "Secure CI/CD Pipeline is running"

if __name__ == "__main__":
# Container listens internally on all interfaces; host exposure is restricted by Docker port binding.
    app.run(host="0.0.0.0", port=5000) # nosec B104
