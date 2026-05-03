pipeline {
    agent any

    stages {

        stage('Checkout') {
            steps {
                echo "🔄 Fetching code..."
                checkout scm
            }
        }

        stage('Build') {
            steps {
                echo "🔧 Build step..."
                bat 'echo Build complete'
            }
        }

        stage('Test') {
            steps {
                echo "🧪 Running tests..."
                bat 'pytest tests/ || exit 1'
            }
        }

        stage('Deploy') {
            steps {
                echo "🚀 Deploying app..."
                bat 'start /B python api/main.py'
            }
        }
    }
}