pipeline {
    agent any
    stages {
        stage('Run Job') {
            steps {
                sh 'pyats run job job/job.py'
            }
        }
        stage('Complete') {
            steps {
                echo 'Job Completed'
            }
        }
    }
}
