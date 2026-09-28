# Secure CI/CD Pipeline

## Project Overview

This project demonstrates the step-by-step development of a secure CI/CD pipeline for a simple Flask web application.

The main goal is not only to run an application inside Docker, but to build a software delivery process where **automation, reproducibility, and security controls** are integrated from the beginning.

The project is being developed incrementally. At the current stage, the Flask application has been containerized, hardened with a non-root runtime user, tested on an Ubuntu EC2 instance, and stored in GitHub.

Future stages will extend the project with:

- GitHub Actions
- Automated testing
- Static Application Security Testing (SAST)
- Dependency vulnerability scanning
- Container image scanning
- Security gates
- Automated deployment

---

# Current Architecture

At the current stage, the application runs as a Docker container on an Ubuntu EC2 instance.

```text
Source Code
    |
    | docker build
    v
Docker Image
secure-cicd-app:1.0
    |
    | docker run
    v
Docker Container
secure-cicd-web
    |
    | 127.0.0.1:5000 -> 5000/tcp
    v
Flask Application
```

The Docker image contains:

- Python runtime
- Flask and required Python dependencies
- Application source code
- A dedicated non-root runtime user
- Runtime configuration
- Container port metadata

---

# Application

The project currently uses a simple Flask web application.

The root endpoint returns:

```text
Secure CI/CD Pipeline is running
```

The application is configured to listen on:

```text
0.0.0.0:5000
```

inside the container.

The relevant Flask configuration is:

```python
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

Using `0.0.0.0` inside the container allows Flask to accept traffic arriving through the container's network interfaces.

The application is currently published on the EC2 host only through:

```text
127.0.0.1:5000
```

This prevents the Flask development server from being directly published on every host network interface.

---

# Dependency Management

Python dependencies are defined in:

```text
requirements.txt
```

Current dependency:

```text
Flask==3.1.3
```

Pinning the dependency version improves reproducibility because the expected version can be installed when the environment is recreated.

The dependency definition was also tested in a clean Python virtual environment using:

```bash
pip install -r requirements.txt
```

This verified that the project environment can be recreated from the dependency file rather than depending on packages that were installed manually on the original system.

This follows an important DevOps principle:

> Environments should be reproducible from configuration and dependency definitions.

---

# Docker Containerization

The Flask application is packaged using Docker.

The current Dockerfile is:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home appuser

COPY app.py .

EXPOSE 5000

USER appuser

CMD ["python", "app.py"]
```

The Dockerfile describes how the application image should be built and how containers created from that image should run.

---

# Dockerfile Design

## Base Image

```dockerfile
FROM python:3.12-slim
```

The project uses the Python 3.12 slim image as its base image.

Instead of manually installing Python inside the container image, the project starts from an existing Python environment.

Conceptually:

```text
python:3.12-slim
        |
        v
Install dependencies
        |
        v
Add application
        |
        v
Configure runtime
        |
        v
Our application image
```

Using a slim base image reduces unnecessary packages compared with a larger general-purpose image.

This can provide:

- Smaller image size
- Faster image transfers
- Fewer unnecessary packages
- Reduced unnecessary attack surface

A smaller image does **not** automatically mean that an image is secure. Additional vulnerability scanning and configuration controls are still required.

---

## Working Directory

```dockerfile
WORKDIR /app
```

The application uses `/app` as its working directory inside the image.

This creates a predictable location for application operations.

After this instruction, relative paths used by later Dockerfile instructions are evaluated relative to:

```text
/app
```

The application structure inside the image is therefore similar to:

```text
/app/
├── app.py
└── requirements.txt
```

---

# Dependency Installation

The dependency definition is copied first:

```dockerfile
COPY requirements.txt .
```

Dependencies are then installed:

```dockerfile
RUN pip install --no-cache-dir -r requirements.txt
```

The `RUN` instruction executes during **image build time**.

Therefore, Flask is installed while the image is being created.

It is not installed every time a container starts.

Conceptually:

```text
docker build
    |
    v
COPY requirements.txt
    |
    v
RUN pip install
    |
    v
Dependencies become part of the image
```

The option:

```text
--no-cache-dir
```

prevents pip from keeping unnecessary package download cache files inside the image.

---

# Docker Build Cache

The dependency definition is intentionally copied before the application source code.

The order is:

```text
COPY requirements.txt
        |
        v
pip install
        |
        v
COPY app.py
```

Application source code is expected to change more frequently than dependency definitions.

If only `app.py` changes:

```text
requirements.txt unchanged
        |
        v
Dependency installation can remain cached
        |
        v
Only application-related layers need rebuilding
```

This improves Docker build efficiency.

A real build demonstrated this behavior:

```text
CACHED WORKDIR /app
CACHED COPY requirements.txt .
CACHED RUN pip install --no-cache-dir -r requirements.txt
CACHED RUN useradd --create-home appuser
COPY app.py .
```

This demonstrates an important Dockerfile design principle:

> Place relatively stable build operations before frequently changing application files when possible.

---

# Docker Image Layers

A Docker image is not simply one large file.

Images are constructed from layers.

A simplified model of this project's image is:

```text
Application Image
+-------------------------------+
| COPY app.py                   |
+-------------------------------+
| Create appuser                |
+-------------------------------+
| Install Python dependencies   |
+-------------------------------+
| COPY requirements.txt         |
+-------------------------------+
| WORKDIR /app                  |
+-------------------------------+
| python:3.12-slim              |
+-------------------------------+
```

Docker can reuse unchanged layers during future builds.

This is the mechanism behind Docker's build cache.

---

# Build Time vs Runtime

One of the important distinctions in Docker is the difference between **build time** and **runtime**.

## Build Time

Build-time instructions prepare the image.

Examples:

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home appuser
COPY app.py .
```

These operations happen during:

```bash
docker build
```

---

## Runtime

Runtime configuration determines what happens when a container is created from the image.

Examples:

```dockerfile
USER appuser
CMD ["python", "app.py"]
```

These become relevant when:

```bash
docker run
```

creates and starts the container.

Simplified lifecycle:

```text
Dockerfile
    |
    | docker build
    v
Docker Image
    |
    | docker run
    v
Docker Container
```

---

# Non-Root Runtime User

A dedicated Linux user is created inside the image:

```dockerfile
RUN useradd --create-home appuser
```

The runtime user is then changed using:

```dockerfile
USER appuser
```

The Flask process therefore does not normally run as root.

This implements the **Principle of Least Privilege**.

The application only receives the permissions required to perform its intended function.

Runtime verification was performed with:

```bash
docker exec secure-cicd-web whoami
```

The result was:

```text
appuser
```

This confirmed that the security configuration was actually active at runtime.

---

# Application File Permissions

Application files inside the container are owned by `root`.

Example:

```text
-rw-rw-r-- 1 root root app.py
-rw-rw-r-- 1 root root requirements.txt
```

The runtime application user can read the source code but does not have permission to modify it.

This was tested using:

```bash
docker exec secure-cicd-web sh -c 'echo test >> /app/app.py'
```

The container returned:

```text
Permission denied
```

This is intentional.

The application needs to:

```text
Read app.py        -> Required
Execute Python     -> Required
Handle HTTP        -> Required
Modify app.py      -> Not required
```

Therefore, unnecessary write access is not granted.

This is another practical application of least privilege.

---

# Container Port Configuration

The Dockerfile contains:

```dockerfile
EXPOSE 5000
```

`EXPOSE` documents that the application expects to provide a service on TCP port 5000.

It does **not** publish the port to the host by itself.

The distinction is:

```text
EXPOSE 5000
    |
    v
Image metadata/documentation
```

while:

```text
docker run -p ...
    |
    v
Actual host-to-container port publishing
```

---

# Controlled Port Publishing

The container is currently started using:

```bash
docker run -d \
  --name secure-cicd-web \
  -p 127.0.0.1:5000:5000 \
  secure-cicd-app:1.0
```

The mapping is:

```text
HOST IP        HOST PORT       CONTAINER PORT

127.0.0.1  :     5000      ->      5000
```

Architecture:

```text
EC2 Host
127.0.0.1:5000
        |
        | Docker port mapping
        v
Docker Container
5000/tcp
        |
        v
Flask Application
```

Binding the host side to `127.0.0.1` prevents the Flask development server from being directly published on all EC2 network interfaces.

Port exposure is therefore deliberately controlled rather than automatically publishing the application to the Internet.

---

# Docker Build Context

The project uses a `.dockerignore` file.

Current configuration:

```text
.git/
.venv/
.venv-test/
__pycache__/
*.pyc
```

The purpose of `.dockerignore` is to prevent unnecessary files from entering the Docker build context.

Examples include:

- Git history
- Local Python virtual environments
- Test environments
- Python cache directories
- Compiled Python cache files

The local Python virtual environment is not copied into the image.

Instead:

```text
requirements.txt
        |
        v
Docker build
        |
        v
Dependencies installed inside clean image
```

This improves reproducibility.

---

# `.gitignore` vs `.dockerignore`

These files serve different tools.

```text
.gitignore
    |
    v
Controls what Git should not track
```

```text
.dockerignore
    |
    v
Controls what Docker should exclude from the build context
```

They may contain similar entries, but they solve different problems.

Neither should be treated as a secret-management system.

---

# Building the Docker Image

The application image is built using:

```bash
docker build -t secure-cicd-app:1.0 .
```

Command breakdown:

```text
docker build
    |
    v
Build a Docker image
```

```text
-t secure-cicd-app:1.0
    |
    v
Assign image name and tag
```

```text
.
    |
    v
Use current directory as build context
```

Result:

```text
Dockerfile
+
app.py
+
requirements.txt
        |
        v
docker build
        |
        v
secure-cicd-app:1.0
```

The image can be listed using:

```bash
docker images
```

---

# Image vs Container

A Docker image and a Docker container are different objects.

## Image

An image is a prepared application package/template.

Example:

```text
secure-cicd-app:1.0
```

It contains the application environment and runtime configuration.

---

## Container

A container is a runtime instance created from an image.

Example:

```text
secure-cicd-web
```

Relationship:

```text
IMAGE
secure-cicd-app:1.0
        |
        | docker run
        v
CONTAINER
secure-cicd-web
```

Multiple containers can be created from one image.

---

# Docker Registry Concept

When an image is not available locally, Docker can retrieve it from a container registry.

This was demonstrated using the `hello-world` image.

The first execution:

```bash
docker run hello-world
```

resulted in the following lifecycle:

```text
Docker checks local images
        |
        v
Image not found
        |
        v
Pull from Docker Hub
        |
        v
Store image locally
        |
        v
Create container
        |
        v
Run container process
```

The image remained available locally after the container exited.

---

# Container Lifecycle

The `hello-world` test was used to demonstrate the relationship between images and containers.

Important distinction:

```text
docker run IMAGE
        |
        v
Create a NEW container
+
Start it
```

while:

```text
docker start CONTAINER
        |
        v
Start an EXISTING container
```

The same image was used to create multiple different containers.

Each container had its own container ID.

---

# Container Process Lifecycle

Containers remain running while their main process remains active.

The `hello-world` container:

```text
Container starts
        |
        v
/hello process runs
        |
        v
Message printed
        |
        v
Process exits
        |
        v
Container stops
```

The Flask container behaves differently:

```text
Container starts
        |
        v
python app.py
        |
        v
Flask starts
        |
        v
Waits for HTTP requests
        |
        v
Process remains active
        |
        v
Container remains running
```

This explains why a stopped container does not necessarily indicate a failure.

---

# Exit Codes

The `hello-world` container exited with:

```text
Exited (0)
```

Exit code `0` normally indicates that the process completed successfully.

Therefore:

```text
Container stopped
```

does not automatically mean:

```text
Container crashed
```

The process may simply have completed its intended work.

---

# Container Management Commands

Running containers can be displayed using:

```bash
docker ps
```

All containers, including stopped containers:

```bash
docker ps -a
```

A running container can be stopped using:

```bash
docker stop <container>
```

A stopped container can be restarted using:

```bash
docker start <container>
```

A container can be removed using:

```bash
docker rm <container>
```

An image can be removed using:

```bash
docker rmi <image>
```

---

# Image and Container Dependency

Docker prevents an image from being removed when an existing container still references that image.

This was demonstrated when:

```bash
docker rmi hello-world
```

returned a conflict because an existing stopped container still referenced the image.

The lifecycle was therefore:

```text
Image
   |
   v
Container exists
   |
   v
Image removal blocked
   |
   v
Remove container
   |
   v
Remove image
```

This demonstrates that an exited container is still an existing Docker object until it is removed.

---

# Container Logging

The Flask container runs in detached mode:

```bash
docker run -d ...
```

The `-d` option runs the container in the background.

Application logs can then be inspected using:

```bash
docker logs secure-cicd-web
```

Example Flask log:

```text
"GET / HTTP/1.1" 200
```

This confirms that the application received and successfully processed an HTTP request.

Container logs are important for:

- Runtime troubleshooting
- Application error investigation
- HTTP request visibility
- Operational monitoring
- Security monitoring

---

# Standard Output and Standard Error

Containerized applications generally write logs to:

```text
stdout
```

and:

```text
stderr
```

Docker captures these streams.

Simplified flow:

```text
Application Process
        |
        v
stdout / stderr
        |
        v
Docker Logging Driver
        |
        v
docker logs
```

This design is important because container platforms can collect application logs centrally.

---

# Runtime Verification

The Flask application was tested using:

```bash
curl http://127.0.0.1:5000/
```

Expected response:

```text
Secure CI/CD Pipeline is running
```

This verified the complete request path:

```text
curl
  |
  v
EC2 localhost:5000
  |
  v
Docker port mapping
  |
  v
Container:5000
  |
  v
Flask
  |
  v
HTTP Response
```

---

# Docker Networking

The container currently uses Docker's default bridge networking.

Observed container networking:

```text
Docker bridge gateway:
172.17.0.1

Container:
172.17.0.2
```

Simplified architecture:

```text
EC2 Host
127.0.0.1:5000
        |
        | Port publishing
        v
Docker Bridge Network
172.17.0.1
        |
        v
Container
172.17.0.2:5000
        |
        v
Flask
```

The `172.17.x.x` addresses are internal Docker network addresses.

They are not the EC2 public IP address.

---

# Docker CLI and Docker Daemon

Docker uses a client/server architecture.

Simplified model:

```text
User
  |
  v
Docker CLI
  |
  v
Docker Socket
  |
  v
Docker Daemon
  |
  v
Container Runtime
  |
  v
Containers
```

Commands such as:

```bash
docker ps
docker build
docker run
docker info
```

are issued using the Docker CLI.

The Docker daemon performs the actual container and image management operations.

---

# Docker Socket

On the Linux host, the Docker CLI communicates with the Docker daemon through:

```text
/var/run/docker.sock
```

Initially, the normal Ubuntu user could use the Docker CLI but could not communicate with the Docker daemon.

This produced a permission error.

The architecture at that point was:

```text
Docker CLI       OK
Docker Daemon    OK
CLI -> Daemon    Permission denied
```

The user was added to the `docker` group to allow access.

---

# Docker Group Security

Membership in the Linux `docker` group is a powerful permission.

Users who can control the Docker daemon may be able to perform highly privileged operations on the host.

Therefore:

> Docker group membership should not be treated as an ordinary low-risk permission.

In production environments, Docker daemon access should be carefully controlled.

---

# Docker Installation Strategy

Docker Engine was installed from Docker's official package repository.

The installation process conceptually followed:

```text
Identify operating system
        |
        v
Check conflicting packages
        |
        v
Install repository prerequisites
        |
        v
Install Docker signing key
        |
        v
Configure official Docker repository
        |
        v
Refresh package metadata
        |
        v
Install Docker Engine components
        |
        v
Verify Docker service
        |
        v
Verify CLI -> daemon communication
```

The exact installation commands are implementation details that can be referenced from official documentation when needed.

Understanding the architecture and verification process is more important than memorizing long installation commands.

---

# Package Signing and Supply Chain Security

The Docker repository signing key was configured as part of package installation.

The purpose of package signing is to help verify that downloaded packages originate from the expected publisher and have not been modified unexpectedly.

Simplified concept:

```text
Software Publisher
        |
        | signs package
        v
Repository
        |
        v
System downloads package
        |
        v
Signature verification
```

This introduces a broader DevSecOps topic:

> Software Supply Chain Security

Later stages of the project can extend this concept to:

- Container image signing
- Software Bill of Materials (SBOM)
- Artifact provenance
- Dependency integrity
- Trusted build pipelines

---

# Image Metadata

The built image was inspected using:

```bash
docker inspect secure-cicd-app:1.0
```

Important image configuration values included:

```text
User: appuser
```

```text
WorkingDir: /app
```

```text
ExposedPorts:
5000/tcp
```

```text
Cmd:
python app.py
```

This demonstrates that a Docker image contains both:

```text
Filesystem layers
+
Runtime configuration metadata
```

Simplified model:

```text
Docker Image
|
├── Filesystem
|   ├── Python
|   ├── Flask
|   ├── /app/app.py
|   └── /app/requirements.txt
|
└── Configuration
    ├── USER = appuser
    ├── WORKDIR = /app
    ├── EXPOSE = 5000/tcp
    └── CMD = python app.py
```

---

# Image Tags vs Image IDs

Image tags are human-readable references.

Example:

```text
secure-cicd-app:1.0
```

An image also has a content-based identifier similar to:

```text
sha256:...
```

Rebuilding an image using the same tag can cause that tag to point to a newer image.

Example:

```text
Before rebuild:

secure-cicd-app:1.0
        |
        v
Image A
```

After rebuild:

```text
secure-cicd-app:1.0
        |
        v
Image B
```

An already-running container created from Image A does not automatically become Image B.

---

# Image Rebuild Does Not Update Running Containers

This behavior was demonstrated during the project.

A container had been created from an earlier image.

The Dockerfile was then modified and a new image was built using the same tag.

The existing running container continued to reference the old image ID.

Therefore:

```text
Dockerfile changes
        |
        v
docker build
        |
        v
New image
```

does **not** mean:

```text
Existing container automatically updated
```

To deploy the new image:

```text
Stop old container
        |
        v
Remove old container
        |
        v
Run new image
        |
        v
Create new container
```

---

# Manual Deployment Workflow

A basic manual deployment was performed.

The process was:

```text
Application / Dockerfile changes
        |
        v
Build new image
        |
        v
Stop old container
        |
        v
Remove old container
        |
        v
Start new container
        |
        v
Verify running state
        |
        v
Verify HTTP response
```

Commands included:

```bash
docker stop secure-cicd-web
```

```bash
docker rm secure-cicd-web
```

```bash
docker run -d \
  --name secure-cicd-web \
  -p 127.0.0.1:5000:5000 \
  secure-cicd-app:1.0
```

Runtime verification:

```bash
docker ps
```

and:

```bash
curl http://127.0.0.1:5000/
```

---

# Deployment Verification

The container's actual image ID was checked using:

```bash
docker inspect -f '{{.Image}}' secure-cicd-web
```

This was compared with the newly built image ID.

The IDs matched, confirming that the new container was created from the expected updated image.

This demonstrates another important DevOps principle:

> Do not assume that deployment succeeded. Verify the running system.

---

# Graceful Container Shutdown

The running application container was stopped using:

```bash
docker stop secure-cicd-web
```

`docker stop` attempts to allow the main container process to terminate cleanly.

This is preferable to immediately forcing process termination when graceful shutdown is possible.

Conceptually:

```text
docker stop
    |
    v
Request graceful termination
```

while a forced termination operation is more abrupt.

Applications may require time to:

- Close connections
- Flush buffers
- Finish active requests
- Perform cleanup

---

# Security Decisions

The current container implementation includes several deliberate security decisions.

## 1. Minimal Base Image

```text
python:3.12-slim
```

is used instead of a larger general-purpose image.

---

## 2. Non-Root Runtime

The application runs as:

```text
appuser
```

instead of root.

---

## 3. Restricted Application File Modification

Application files are root-owned.

The non-root application user can read them but cannot modify them.

---

## 4. Controlled Port Publishing

The service is published only to:

```text
127.0.0.1:5000
```

instead of every host network interface.

---

## 5. Reduced Build Context

`.dockerignore` prevents unnecessary files from entering the Docker build context.

---

## 6. Reproducible Dependency Definition

Python dependencies are defined in:

```text
requirements.txt
```

instead of relying on manually installed host packages.

---

## 7. Runtime Verification

Security assumptions such as the non-root runtime user were tested against the running container rather than being assumed from the Dockerfile.

---

# Least Privilege

The Principle of Least Privilege appears multiple times in the project.

Examples include:

```text
GitHub token
    |
    v
Only required repository permissions
```

```text
Container runtime
    |
    v
appuser instead of root
```

```text
Application source
    |
    v
Runtime user can read but does not need write access
```

The principle can be summarized as:

> Give users, applications, credentials, and services only the permissions required to perform their intended function.

---

# Important Secret Management Note

`.gitignore` and `.dockerignore` are not secret-management systems.

If sensitive information such as:

- API tokens
- Passwords
- Private keys
- Credentials
- Environment secrets

is committed to Git, adding the file to `.gitignore` later does not remove it from Git history.

A compromised credential should generally be considered exposed and rotated.

Future pipeline stages will introduce stronger secret-handling practices.

---

# Development vs Production

The application currently uses Flask's built-in development server.

Flask produces the warning:

```text
WARNING: This is a development server.
Do not use it in a production deployment.
```

Dockerizing the application does not automatically make the application production-ready.

Docker solves packaging and environment consistency problems.

It does not automatically provide a production-grade application server.

A future production-oriented architecture could look like:

```text
Client
  |
  v
Nginx
  |
  v
Production WSGI Server
  |
  v
Flask Application
```

A production WSGI server such as Gunicorn may be introduced later.

---

# Git Workflow

Changes are tracked using Git.

The basic workflow used in the project is:

```text
Modify files
    |
    v
git status
    |
    v
git diff
    |
    v
git add
    |
    v
git commit
    |
    v
git push
    |
    v
GitHub
```

Important distinction:

```text
git commit
```

stores a change in the local Git history.

```text
git push
```

sends local commits to the remote repository.

---

# GitHub Repository

GitHub acts as the remote Git repository.

The repository currently stores configuration required to recreate the application environment, including:

```text
app.py
requirements.txt
Dockerfile
.dockerignore
.gitignore
README.md
```

The following are intentionally **not** stored in Git:

```text
.venv/
.venv-test/
```

because they are locally generated Python environments.

---

# Reproducibility

Reproducibility is one of the main design goals of this project.

Instead of manually reconstructing an environment, the required configuration is stored as code.

Examples:

```text
requirements.txt
    |
    v
Recreate Python dependencies
```

```text
Dockerfile
    |
    v
Recreate container image
```

```text
Git repository
    |
    v
Recreate source/configuration history
```

This moves the project from:

```text
"Configure the machine manually"
```

toward:

```text
"Describe the environment and rebuild it predictably"
```

---

# Current Repository Structure

```text
secure-cicd-pipeline/
|
├── .dockerignore
├── .gitignore
├── Dockerfile
├── README.md
├── app.py
└── requirements.txt
```

Additional CI/CD and security configuration files will be added as the project progresses.

---

# Current Project Status

## Application and Git

- [x] Create simple Flask application
- [x] Initialize Git repository
- [x] Configure Git identity
- [x] Connect local repository to GitHub
- [x] Push project to GitHub
- [x] Configure `.gitignore`

## Python Dependencies

- [x] Install Python package tooling
- [x] Create Python virtual environment
- [x] Install Flask
- [x] Create `requirements.txt`
- [x] Test dependencies in a clean virtual environment
- [x] Pin Flask dependency version

## Docker Environment

- [x] Install Docker Engine
- [x] Install Docker CLI
- [x] Verify Docker daemon
- [x] Configure user access to Docker daemon
- [x] Verify Docker CLI-to-daemon communication
- [x] Test Docker using `hello-world`

## Docker Fundamentals

- [x] Understand registry concept
- [x] Understand image concept
- [x] Understand container concept
- [x] Understand `docker run`
- [x] Understand `docker start`
- [x] Understand running vs stopped containers
- [x] Understand container exit codes
- [x] Understand image/container removal
- [x] Understand image-to-container relationships

## Containerization

- [x] Create `.dockerignore`
- [x] Create Dockerfile
- [x] Use Python slim base image
- [x] Configure application working directory
- [x] Install dependencies during image build
- [x] Optimize Dockerfile ordering for build cache
- [x] Add Flask source code
- [x] Configure non-root application user
- [x] Configure port metadata
- [x] Configure container startup command
- [x] Build custom Docker image

## Runtime Security

- [x] Run application as non-root user
- [x] Verify runtime user with `docker exec`
- [x] Verify application file permissions
- [x] Confirm runtime user cannot modify application source
- [x] Avoid privileged container execution
- [x] Bind published application port to localhost only

## Runtime Operations

- [x] Run Flask container
- [x] Verify running container with `docker ps`
- [x] Verify HTTP response using `curl`
- [x] Inspect application logs
- [x] Inspect image metadata
- [x] Inspect container metadata
- [x] Inspect Docker network information
- [x] Rebuild image after source/configuration changes
- [x] Replace old container with container from updated image
- [x] Verify deployed image ID

## Documentation

- [x] Push Dockerfile to GitHub
- [x] Push `.dockerignore` to GitHub
- [x] Push container-compatible Flask configuration
- [x] Document current architecture and security decisions

---

# Next Stage: CI/CD Automation

The next major stage introduces GitHub Actions.

The current workflow is mostly manual:

```text
Developer changes code
        |
        v
git commit
        |
        v
git push
        |
        v
Manual Docker build
        |
        v
Manual verification
        |
        v
Manual deployment
```

The target workflow is:

```text
Developer
    |
    | git push
    v
GitHub
    |
    v
GitHub Actions
    |
    +-----------------------+
    |                       |
    v                       v
Automated Tests        Security Checks
    |                       |
    +-----------+-----------+
                |
                v
          Docker Build
                |
                v
         Image Security Scan
                |
                v
          Security Gate
                |
                v
            Deployment
```

---

# Planned CI/CD Stages

The planned pipeline will include:

## Automated Tests

Validate application behavior before creating a deployable artifact.

---

## Static Application Security Testing

Planned tools:

```text
Semgrep
or
Bandit
```

Purpose:

> Analyze source code for potentially insecure patterns.

---

## Dependency Scanning

Planned tool:

```text
pip-audit
```

Purpose:

> Identify known vulnerabilities in third-party Python dependencies.

---

## Docker Image Build

The CI pipeline will automatically build the application image rather than relying on a developer manually running:

```bash
docker build
```

---

## Container Image Scanning

Planned tool:

```text
Trivy
```

Purpose:

> Scan the built container image for known vulnerabilities and insecure components.

---

## Security Gates

Security checks will eventually be able to prevent unsafe artifacts from progressing through the pipeline.

Conceptually:

```text
Security check passes
        |
        v
Continue pipeline
```

```text
Security check fails
        |
        v
Stop pipeline
```

This represents one of the central ideas of DevSecOps:

> Security should be integrated into the delivery workflow rather than performed only after deployment.

---

# Future Deployment Automation

The manual deployment process currently looks like:

```text
Build image
    |
    v
Stop container
    |
    v
Remove container
    |
    v
Start new container
    |
    v
Verify application
```

A later pipeline stage will automate this workflow.

The final goal is to move toward:

```text
git push
    |
    v
Automated validation
    |
    v
Security checks
    |
    v
Image build
    |
    v
Image scan
    |
    v
Deployment
    |
    v
Runtime verification
```

---

# Key Concepts Demonstrated

The project currently demonstrates practical understanding of:

- Git version control
- GitHub remote repositories
- Python dependency management
- Dependency reproducibility
- Docker architecture
- Docker CLI
- Docker daemon
- Docker socket permissions
- Docker registries
- Docker images
- Docker containers
- Image layers
- Docker build cache
- Docker build contexts
- `.dockerignore`
- Dockerfile design
- Build-time vs runtime operations
- Container networking
- Docker bridge networking
- Port publishing
- Container process lifecycle
- Container exit codes
- Container logs
- Image metadata
- Container metadata
- Non-root container execution
- Linux file permissions
- Least privilege
- Manual container deployment
- Runtime verification
- Basic software supply-chain concepts
- Development vs production architecture

---

# Security Principles Applied

The project currently applies the following security principles:

### Least Privilege

Services and users receive only the permissions required for their role.

### Reduced Attack Surface

A slim base image is used rather than an unnecessarily large runtime image.

### Controlled Exposure

The Flask development server is bound to the host loopback interface rather than directly published on every host interface.

### Reproducibility

Dependencies and runtime configuration are defined in files rather than relying on undocumented manual configuration.

### Runtime Verification

Security assumptions are tested against the actual running container.

### Build Context Minimization

Unnecessary local files are excluded from Docker builds.

### Separation of Build and Runtime Concerns

Image preparation occurs during build time while application execution occurs using a dedicated runtime user.

---

# Current Limitations

The current implementation is intentionally still a learning/development environment.

Known limitations include:

- Flask development server is still being used
- No automated CI/CD pipeline yet
- No SAST yet
- No dependency vulnerability scanning yet
- No container image vulnerability scanning yet
- No automated security gate yet
- No automated deployment yet
- No dedicated production WSGI server yet
- No centralized secret-management solution yet
- No image signing yet
- No SBOM generation yet

These controls will be introduced incrementally as the project progresses.

---

# Learning Goal

The purpose of this repository is not simply to collect configuration files.

Each stage is implemented manually first in order to understand:

```text
What problem exists?
        |
        v
Why a tool is needed
        |
        v
How the tool works
        |
        v
How it fits into the architecture
        |
        v
How security affects the design
        |
        v
How the process can be automated
```

The final goal is to build a complete DevSecOps workflow while understanding the architecture and security reasoning behind each component.
