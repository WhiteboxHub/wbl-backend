"""
YouTube client for uploading video recordings in background tasks.
"""


class YouTubeClient:

    def upload_unlisted_video(self, assessment_id: int, local_file_path: str) -> str:
        """Background worker uploading WebM video to YouTube."""
        print(
            f"[YouTubeClient] Processing background YouTube upload for assessment {assessment_id} from {local_file_path}"
        )
        return f"https://youtube.com/watch?v=mock_{assessment_id}"
