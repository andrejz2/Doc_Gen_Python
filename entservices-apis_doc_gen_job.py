import os
import subprocess
import sys
import shutil
import json
import argparse
import datetime

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

def clone_repo(branch, github_creds, user_name):
    """Stage: Clone Repository"""
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
    git log --since='9 days ago' --pretty=format: --name-only | grep "^{apis_folder}/.*/I.*\\.h$" || true
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

def push_files_to_branch(docs_folder, github_creds, user_email, user_name):
    """Stage: Push Files to Branch"""
    stage_decl_cmd = "echo 'Stage: Push Files to Branch'"
    run_command(stage_decl_cmd)

    # unique branch name using date (keeps track of doc updates for different weeks)
    date_suffix = datetime.datetime.now().strftime('%Y%m%d')
    unique_branch_name = f"update-docs-{date_suffix}"
    new_branch_cmd = "echo 'New branch created: {unique_branch_name}'"
    run_command(new_branch_cmd)

    rebase_or_push_cmd = f"""
    cd entservices-apis
    git fetch origin
    git checkout develop
    git pull origin develop
    git checkout -B {unique_branch_name} origin/develop
    rm -rf tools/md_from_h_generator/generated_docs/test.md
    cp -r tools/md_from_h_generator/generated_docs/*.md {docs_folder}/apis/ || echo "No files to copy."
    git config --global user.email "{user_email}"
    git config --global user.name "{user_name}"
    git add {docs_folder}/apis/*.md
    git commit -m "Automated update of documentation ({date_suffix})" || echo "Nothing to commit."
    git push https://{user_name}:{github_creds}@github.com/rdkcentral/entservices-apis.git {unique_branch_name} || echo "Push failed."
    """
    try:
        run_command(rebase_or_push_cmd)
        return unique_branch_name
    except Exception as e:
        print(f"Failed to push branch: {e}")
        sys.exit(1)

def create_pull_request(github_creds, user_name, github_repo, branch, unique_branch_name):
    """Stage: Create Pull Request"""
    stage_decl_cmd = "echo 'Stage: Create Pull Request'"
    run_command(stage_decl_cmd)

    pr_data = {
        "title": f"Automated update of documentation ({doc_branch_name})",
        "body": f"This is an automated pull request to update documentation. Generated from branch {doc_branch_name}.",
        "head": unique_branch_name,
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
        clone_repo('develop', GITHUB_CREDS, USER_NAME)
        changed_files = check_for_changes(APIS_FOLDER)
        process_changed_files(changed_files)
        unique_branch_name = push_files_to_branch(DOCS_FOLDER, GITHUB_CREDS, USER_EMAIL, USER_NAME)
        create_pull_request(GITHUB_CREDS, USER_NAME, GITHUB_REPO, BRANCH, unique_branch_name)
        print("Pipeline completed successfully!")
    except Exception as e:
        print(f"Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
