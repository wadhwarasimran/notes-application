pipeline {

    agent any

    options {
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '15'))
    }

    environment {
        // ---- CHANGE THIS to your own GitHub username, in lowercase ------------
        // Actions had ${GITHUB_REPOSITORY_OWNER,,} for free. Jenkins has never
        // heard of GitHub, so you supply it — and lowercase matters: GHCR refuses
        // capitals in the owner segment.
        OWNER = 'sohamkaralkar'

        // Deliberately NOT "notes-api". GHCR ties a package to the repo that first
        // published it, so reusing the CI lecture's package name gets you
        //     denied: permission_denied: write_package
        IMAGE_NAME  = 'notes-application'
        GITOPS_REPO = 'notes-gitops'
        MANIFEST    = 'apps/notes-api/deployment.yaml'

        IMAGE = "ghcr.io/${OWNER}/${IMAGE_NAME}"

        // NOT 8080. On this laptop 8080 is the kind ingress and 8090 is Jenkins.
        // The Actions workflow can use 8080 because its runner is a throwaway VM;
        // you cannot.
        TEST_PORT = '18087'
    }

    stages {

        stage('Checkout') {
            steps {
                script {
                    // Take the SHA from what checkout RETURNS. env.GIT_COMMIT is
                    // not populated in every job type, and when it isn't you get
                    // "Cannot invoke method take() on null object" on build #1.
                    def scmVars = checkout scm
                    env.SHA = scmVars.GIT_COMMIT          // full 40 chars, like $GITHUB_SHA
                }
                echo "Building ${env.IMAGE}:${env.SHA}"
            }
        }

        stage('Build') {
            steps {
                sh '''
                    docker build -t "$IMAGE:$SHA" -t "$IMAGE:latest" .
                '''
            }
        }

        // THE GATE. Run the container and prove the app answers BEFORE anything
        // is published. If this fails the build stops and nothing reaches GHCR.
        //
        // This is where the Actions workflow does NOT translate literally. It
        // curls localhost, because on a GitHub runner the container and the
        // workflow share a host. Jenkins is itself a container: the image it just
        // built starts as a SIBLING, created by the same daemon through the
        // mounted socket. `localhost` from in here is Jenkins, not the app — so
        // we ask the daemon for the sibling's bridge IP.
        stage('Smoke test') {
            steps {
                sh '''
                    docker rm -f smoke >/dev/null 2>&1 || true
                    docker run -d --name smoke -p "$TEST_PORT:8080" "$IMAGE:$SHA"

                    IP="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' smoke)"
                    echo "sibling container is at $IP:8080"

                    for _ in $(seq 1 20); do
                        curl -fsS "http://$IP:8080/healthz" >/dev/null && break || sleep 1
                    done

                    curl -fsS "http://$IP:8080/healthz"
                    curl -fsS "http://$IP:8080/ready"
                '''
            }
            post {
                always { sh 'docker rm -f smoke >/dev/null 2>&1 || true' }
            }
        }

        stage('Push to GHCR') {
            steps {
                withCredentials([usernamePassword(
                        credentialsId: 'ghcr-credentials',
                        usernameVariable: 'GHCR_USER',
                        passwordVariable: 'GHCR_PAT')]) {
                    // SINGLE quotes. With double quotes Groovy would substitute the
                    // token into the command line before the shell saw it — and
                    // Jenkins echoes every command it runs into the build log.
                    sh '''
                        echo "$GHCR_PAT" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
                        docker push "$IMAGE:$SHA"
                        docker logout ghcr.io
                    '''
                }
            }
        }

        // ───────────── THE HANDOFF: CI ends, CD begins ─────────────
        // The whole point. CI does not deploy — it writes one line into another
        // repo, and a robot inside the cluster does the rest.
        stage('Deploy: write the tag into notes-gitops') {
            steps {
                withCredentials([usernamePassword(
                        credentialsId: 'gitops-token',
                        usernameVariable: 'GITOPS_USER',
                        passwordVariable: 'GITOPS_TOKEN')]) {
                    sh '''
                        rm -rf gitops
                        # The clone is anonymous — notes-gitops is public. Only the
                        # PUSH needs the token, and we pass it as a one-shot URL so
                        # it never gets written into .git/config in the workspace.
                        git clone --depth 1 "https://github.com/$OWNER/$GITOPS_REPO.git" gitops
                        cd gitops

                        # Match ANY ghcr.io image line, not just this image name: the
                        # manifest ships pointing at the course's public image so the
                        # first sync works, and this is the commit that switches it.
                        sed -i -E "s#(image: )ghcr\\.io/.*#\\1$IMAGE:$SHA#" "$MANIFEST"

                        git config user.name  "jenkins-ci"
                        git config user.email "jenkins-ci@users.noreply.github.com"
                        git add "$MANIFEST"

                        if git diff --cached --quiet; then
                            echo "image tag unchanged — nothing to deploy"
                            exit 0
                        fi

                        git commit -m "deploy $IMAGE_NAME:$SHA"
                        git push "https://$GITOPS_USER:$GITOPS_TOKEN@github.com/$OWNER/$GITOPS_REPO.git" HEAD:main

                        echo "wrote $IMAGE:$SHA into $GITOPS_REPO/$MANIFEST"
                        echo "Argo CD will pick it up and sync the cluster."
                    '''
                }
            }
        }
    }

    post {
        success {
            echo "Deployed ${env.IMAGE}:${env.SHA} — Argo CD takes it from here."
        }
        failure {
            echo 'FAILED — read the red stage in the Stage View.'
        }
        always {
            sh 'docker image prune -f >/dev/null 2>&1 || true'
            cleanWs()
        }
    }
}