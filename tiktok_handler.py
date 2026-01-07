import logging
import yt_dlp
import os
import tempfile
import glob

logger = logging.getLogger(__name__)

def download_tiktok_video(video_url, output_folder=None):
    """
    Downloads a TikTok video from a given URL using yt-dlp.
    
    Args:
        video_url: The TikTok video URL to download
        output_folder: Optional folder to save the video. If None, uses a temporary directory.
    
    Returns:
        dict: A dictionary containing:
            - 'success': bool indicating if download was successful
            - 'filepath': str path to the downloaded video file (if successful)
            - 'title': str title of the video (if available)
            - 'error': str error message (if unsuccessful)
    """
    
    if output_folder is None:
        output_folder = tempfile.gettempdir()
    
    # Configuration options for yt-dlp
    ydl_opts = {
        'format': 'best',  # Download the best quality available
        'outtmpl': f'{output_folder}/%(id)s.%(ext)s',  # Use video ID for safe filename
        'noplaylist': True,  # Ensure we only download a single video, not a playlist
        'quiet': True,      # Minimize terminal output
        'no_warnings': True,
    }

    try:
        logger.info(f"Attempting to download TikTok video: {video_url}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first to get the title and filepath
            info = ydl.extract_info(video_url, download=False)
            video_title = info.get('title', 'Unknown Title')
            
            logger.info(f"Found TikTok video: {video_title}")
            
            # Perform the download
            info = ydl.extract_info(video_url, download=True)
            
            # Get the filepath
            filepath = ydl.prepare_filename(info)
            
            # Verify the file was actually downloaded
            if not os.path.exists(filepath):
                # Try to find the file with the video ID
                video_id = info.get('id', '')
                logger.warning(f"Expected file not found at {filepath}, searching for video ID: {video_id}")
                possible_files = glob.glob(f"{output_folder}/{video_id}.*")
                if possible_files:
                    # Use the first match (should only be one)
                    filepath = possible_files[0]
                    logger.info(f"Found file: {filepath}")
                else:
                    raise FileNotFoundError(f"Downloaded file not found for video ID: {video_id}")
            
        logger.info(f"Successfully downloaded TikTok video: {video_title} to {filepath}")
        
        return {
            'success': True,
            'filepath': filepath,
            'title': video_title
        }

    except (OSError, IOError) as e:
        logger.error(f"File system error downloading TikTok video: {e}")
        return {
            'success': False,
            'error': f"File system error: {str(e)}"
        }
    except Exception as e:
        # Catch yt-dlp exceptions and other unexpected errors
        logger.error(f"Error downloading TikTok video: {e}")
        return {
            'success': False,
            'error': str(e)
        }
