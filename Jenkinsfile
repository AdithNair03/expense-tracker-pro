// Jenkins Pipeline for Spendwise.
//
// What it does, on every push to GitHub:
//   1. Run the test suite and lint
//   2. Build the production Docker image
//   3. Push it to Docker Hub, tagged with both the Jenkins build number and `latest`
//
// Requires a Jenkins credential of type "Username with password" with ID
// "dockerhub-creds" (Docker Hub username + a Read&Write access token as the password).
// Set up in: Jenkins -> Manage Jenkins -> Credentials -> (global) -> Add Credentials.

pipeline {
    agent any

    environment {
        DOCKERHUB_CREDENTIALS = credentials('dockerhub-creds')
        IMAGE_NAME = "nairadith05/expense-tracker-pro"
    }

    stages {
        stage('Test') {
            // Runs directly inside the Jenkins container itself (which has Python
            // installed - see jenkins/Dockerfile) rather than spinning up a separate
            // Docker agent container: Jenkins here is borrowing the host's Docker engine
            // (not running its own), so a `docker` agent's workspace-mounting doesn't
            // resolve correctly. Running tests in-container sidesteps that entirely.
            steps {
                sh '''
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --no-cache-dir -r requirements-dev.txt
                    flake8
                    pytest -q --cov=app
                '''
            }
        }

        stage('Build image') {
            steps {
                script {
                    dockerImage = docker.build("${IMAGE_NAME}:${BUILD_NUMBER}")
                }
            }
        }

        stage('Push image') {
            steps {
                script {
                    docker.withRegistry('', 'dockerhub-creds') {
                        dockerImage.push("${BUILD_NUMBER}")
                        dockerImage.push("latest")
                    }
                }
            }
        }
    }

    post {
        always {
            // Clean up images built on the Jenkins host so disk doesn't fill up over time.
            sh "docker rmi ${IMAGE_NAME}:${BUILD_NUMBER} || true"
        }
        success {
            echo "Build #${BUILD_NUMBER} passed tests and pushed ${IMAGE_NAME}:${BUILD_NUMBER} and :latest to Docker Hub."
        }
        failure {
            echo "Build #${BUILD_NUMBER} failed - check the Test stage first, that's almost always it."
        }
    }
}
