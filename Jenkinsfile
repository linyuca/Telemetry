pipeline {
    agent any
    stages {
        stage('Install python3') {
            steps {
                sh 'sudo apt-get install python3'
            }
        }
        stage('Install pip3') {
            steps {
                sh 'sudo apt-get install python3-pip'
            }
        }
        stage('Install pyats') {
            steps {
                sh 'sudo pip3 install "pyats[full]"'
            }
        }
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
