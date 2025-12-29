import os
from huggingface_hub import HfApi, Repository, create_repo
from typing import Optional

def sync_from_hf(repo_id: str, local_dir: str, token: Optional[str] = None):
    """Clones or pulls a dataset from HF."""
    if not os.path.exists(local_dir):
        os.makedirs(local_dir, exist_ok=True)
    
    repo = Repository(local_dir=local_dir, clone_from=repo_id, token=token)
    repo.git_pull()
    return local_dir

def sync_to_hf(repo_id: str, local_dir: str, commit_message: str = "Update dataset via mission editor", token: Optional[str] = None):
    """Pushes local dataset to HF."""
    api = HfApi(token=token)
    
    # Ensure repo exists
    try:
        api.repo_info(repo_id=repo_id, repo_type="dataset")
    except Exception:
        create_repo(repo_id=repo_id, repo_type="dataset", token=token)
        
    repo = Repository(local_dir=local_dir, clone_from=repo_id, token=token)
    repo.git_add(pattern=".", auto_lfs_track=True)
    repo.git_commit(commit_message)
    repo.git_push()
