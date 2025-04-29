import os
import subprocess
import sys
import shutil
import json
import argparse

def run_command(command, cwd=None, capture_output=False):
    """Run a shell command and handle errors."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            text=True,
            capture_output=capture_output,
            check=True
        )
        return result.stdout.strip() if capture_output else None
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"Error message: {e.stderr if e.stderr else e}")
        sys.exit(1)

def checkout_code(apis_folder, docs_folder, tools_folder, github_repo, branch, github_creds):
    """Stage: Checkout"""
    print("Stage: Checkout")
    if os.path.exists('entservices-apis'):
        shutil.rmtree('entservices-apis')
    os.makedirs('entservices-apis', exist_ok=True)

    commands = f"""
    git init entservices-apis
    cd entservices-apis
    git config core.sparseCheckout true
    echo "{apis_folder}" >> .git/info/sparse-checkout
    echo "{docs_folder}" >> .git/info/sparse-checkout
    echo "{tools_folder}" >> .git/info/sparse-checkout
    git remote add origin https://{github_creds}@github.com/{github_repo}.git
    git fetch origin {branch}
    git reset --hard origin/{branch}
    """
    run_command(commands)

def check_for_changes(apis_folder):
    """Stage: Check for Changes"""
    print("Stage: Check for Changes")
    command = f"""
    cd entservices-apis
    git log --since='8 days ago' --pretty=format: --name-only | grep "^{apis_folder}/.*\\.h$" || true
    """
    changed_files = run_command(command, capture_output=True)
    if changed_files:
        print(f"Changed .h files in the last week:\n{changed_files}")
        return changed_files.splitlines()
    else:
        print("No .h files changed in the last week.")
        sys.exit(0)

def process_changed_files(changed_files):
    """Stage: Process Changed Files"""
    print("Stage: Process Changed Files")
    failed_files = []

    for file in changed_files:
        try:
            print(f"Processing file: {file}")
            command = f"""
            cd entservices-apis
            python3 tools/md_from_h_generator/generate_md_from_header.py {file}
            """
            run_command(command)
        except Exception as e:
            print(f"Failed to process file: {file}")
            failed_files.append(file)

    if failed_files:
        print(f"The following files failed to process:\n{failed_files}")
        with open('logs/failed_files.log', 'w') as log_file:
            log_file.write('\n'.join(failed_files))

def create_pull_request(docs_folder, github_creds, github_repo, branch, user_email, user_name):
    """Stage: Create Pull Request"""
    print("Stage: Create Pull Request")
    commands = f"""
    cd entservices-apis
    cp -r tools/md_from_h_generator/generated_docs/*.md {docs_folder}/apis/ || echo "No files to copy."
    rm -rf tools/md_from_h_generator/generated_docs/*
    git config --global user.email "{user_email}"
    git config --global user.name "{user_name}"
    git checkout -b update-docs
    git add {docs_folder}/*
    git commit -m "Automated update of documentation" || echo "Nothing to commit."
    git push -f https://{github_creds}@github.com/{github_repo}.git update-docs || echo "Push failed."
    """
    run_command(commands)

    pr_data = {
        "title": "Automated update of documentation",
        "body": "This is an automated pull request to update the documentation.",
        "head": "update-docs",
        "base": branch
    }
    pr_command = f"""
    curl -X POST -H "Authorization: token {github_creds}" \
        -H "Accept: application/vnd.github.v3+json" \
        https://api.github.com/repos/{github_repo}/pulls \
        -d '{json.dumps(pr_data)}'
    """
    run_command(pr_command)

def main():
    parser = argparse.ArgumentParser(description="Run the documentation generation job.")
    parser.add_argument("-u", "--username", required=True, help="GitHub username")
    parser.add_argument("-p", "--password", required=True, help="GitHub token")
    parser.add_argument("-b", "--branch", required=True, help="Branch name")
    parser.add_argument("-r", "--repo", required=True, help="GitHub repository")
    args = parser.parse_args()

    GITHUB_REPO = args.repo
    BRANCH = args.branch
    USER_NAME = args.username
    GITHUB_CREDS = args.password
    USER_EMAIL = 'azerom960@cable.comcast.com'
    APIS_FOLDER = 'apis'
    DOCS_FOLDER = 'docs'
    TOOLS_FOLDER = 'tools'

    try:
        checkout_code(APIS_FOLDER, DOCS_FOLDER, TOOLS_FOLDER, GITHUB_REPO, 'develop', GITHUB_CREDS)
        changed_files = check_for_changes(APIS_FOLDER)
        process_changed_files(changed_files)
        create_pull_request(DOCS_FOLDER, GITHUB_CREDS, GITHUB_REPO, BRANCH, USER_EMAIL, USER_NAME)
        print("Pipeline completed successfully!")
    except Exception as e:
        print(f"Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
