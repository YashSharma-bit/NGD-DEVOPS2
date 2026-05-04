pipeline {
    agent any

    stage('Checkout') {
    steps {
        echo "🔄 Cleaning workspace and fetching latest code..."

        deleteDir()

        git branch: 'main',
            url: 'https://github.com/YashSharma-bit/NGD-DEVOPS2'
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