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

def checkout_code(branch, github_creds, user_name):
    """Stage: Checkout"""
    stage_decl_cmd = "echo 'Stage: Checkout'"
    run_command(stage_decl_cmd)

    if os.path.exists('entservices-apis'):
        shutil.rmtree('entservices-apis')
    os.makedirs('entservices-apis', exist_ok=True)
    clone_cmd = f"git clone --branch {branch} https://{user_name}:{github_creds}@github.com/rdkcentral/entservices-apis.git entservices-apis"
    run_command(clone_cmd)

def check_for_changes(apis_folder):
    """Stage: Check for Changes"""
    stage_decl_cmd = "echo 'Stage: Check for Changes'"
    run_command(stage_decl_cmd)

    check_changes_cmd = f"""
    cd entservices-apis
    git log --since='8 days ago' --pretty=format: --name-only | grep "^{apis_folder}/.*/I.*\\.h$" || true
    """
    changed_files = run_command(check_changes_cmd, capture_output=True)
    if changed_files:
        for file in changed_files.splitlines():
            run_command(f"echo {file}")
            return changed_files.splitlines()
    else:
        run_command('echo "No .h files changed in the last week."')
        sys.exit(0)

def process_changed_files(changed_files):
    """Stage: Process Changed Files"""
    stage_decl_cmd = "echo 'Stage: Process Changed Files'"
    run_command(stage_decl_cmd)

    failed_files = []
    for file in changed_files:
        if file == "apis/Ids.h":
            continue
        try:
            run_command(f"echo 'Processing file: {file}'")
            run_doc_gen_script_cmd = f"""
            cd entservices-apis
            python3 tools/md_from_h_generator/generate_md_from_header.py {file}
            """
            run_command(run_doc_gen_script_cmd)
        except Exception as e:
            run_command(f"echo 'Failed to process {file}: {e}'")
            failed_files.append(file)

    if failed_files:
        for file in failed_files:
            run_command(f"echo 'Failed to process file: {file}'")
        with open('logs/failed_files.log', 'w') as log_file:
            log_file.write('\n'.join(failed_files))

def create_pull_request(docs_folder, github_creds, github_repo, branch, user_email, user_name):
    """Stage: Create Pull Request"""
    commands = f"""
    cd entservices-apis
    git fetch origin
    git checkout develop
    git pull origin develop
    git checkout -b update-docs
    git pull --rebase origin update-docs || true
    git rebase origin/develop || git merge origin/develop
    rm -rf tools/md_from_h_generator/generated_docs/test.md
    cp -r tools/md_from_h_generator/generated_docs/*.md {docs_folder}/apis/ || echo "No files to copy."
    git config --global user.email "{user_email}"
    git config --global user.name "{user_name}"
    git add {docs_folder}/*
    git commit -m "Automated update of documentation" || echo "Nothing to commit."
    git push https://{user_name}:{github_creds}@github.com/rdkcentral/entservices-apis.git update-docs || echo "Push failed."
    """
    run_command(commands)

    pr_check_cmd = f"""
    curl -s -H "Authorization: token {github_creds}" \
        "https://api.github.com/repos/{github_repo}/pulls?head=update-docs&base={branch}"
    """
    pr_check_result = run_command(pr_check_cmd, capture_output=True)
    if pr_check_result and pr_check_result.strip() != "[]":
        run_command("echo 'A pull request for 'update-docs' already exists. Skipping PR creation.'")
        return

    pr_data = {
        "title": "Automated update of documentation",
        "body": "This is an automated pull request to update the documentation.",
        "head": "update-docs",
        "base": branch
    }
    pr_cmd = f"""
    curl -X POST -H "Authorization: token {github_creds}" \
        -H "Accept: application/vnd.github.v3+json" \
        https://api.github.com/repos/{github_repo}/pulls \
        -d '{json.dumps(pr_data)}'
    """
    run_command(pr_cmd)

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

    try:
        checkout_code('develop', GITHUB_CREDS, USER_NAME)
        changed_files = check_for_changes(APIS_FOLDER)
        process_changed_files(changed_files)
        create_pull_request(DOCS_FOLDER, GITHUB_CREDS, GITHUB_REPO, BRANCH, USER_EMAIL, USER_NAME)
        print("Pipeline completed successfully!")
    except Exception as e:
        print(f"Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
