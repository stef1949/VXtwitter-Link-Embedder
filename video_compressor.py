import logging
import os
import ffmpeg
import tempfile

logger = logging.getLogger(__name__)

def compress_video(input_path, target_size_mb=10, output_path=None):
    """
    Compress a video file to meet the target size using ffmpeg.
    
    Args:
        input_path: Path to the input video file
        target_size_mb: Target size in megabytes (default: 10MB for Discord)
        output_path: Optional output path. If None, creates a temp file.
    
    Returns:
        dict: A dictionary containing:
            - 'success': bool indicating if compression was successful
            - 'filepath': str path to the compressed video file (if successful)
            - 'original_size': int original file size in bytes
            - 'compressed_size': int compressed file size in bytes
            - 'error': str error message (if unsuccessful)
    """
    
    try:
        # Get original file size
        original_size = os.path.getsize(input_path)
        logger.info(f"Original video size: {original_size / (1024 * 1024):.2f} MB")
        
        # If file is already under target, return original
        if original_size <= target_size_mb * 1024 * 1024:
            logger.info(f"Video is already under {target_size_mb}MB, no compression needed")
            return {
                'success': True,
                'filepath': input_path,
                'original_size': original_size,
                'compressed_size': original_size
            }
        
        # Create output path if not provided
        if output_path is None:
            temp_dir = tempfile.gettempdir()
            base_name = os.path.basename(input_path)
            name, ext = os.path.splitext(base_name)
            output_path = os.path.join(temp_dir, f"{name}_compressed{ext}")
        
        # Get video duration and calculate target bitrate
        try:
            probe = ffmpeg.probe(input_path)
            duration = float(probe['format']['duration'])
            logger.info(f"Video duration: {duration:.2f} seconds")
        except Exception as e:
            logger.warning(f"Could not probe video duration: {e}, using default compression")
            duration = None
        
        # Calculate target bitrate to achieve target file size
        # target_size (MB) * 8 (bits per byte) * 1024 (KB per MB) / duration (s) = bitrate (kbps)
        # Use 90% of target to leave room for audio and overhead
        if duration:
            target_bitrate_kbps = int((target_size_mb * 8 * 1024 * 0.9) / duration)
            # Set reasonable bounds: minimum 100kbps, maximum 2000kbps
            target_bitrate_kbps = max(100, min(target_bitrate_kbps, 2000))
            logger.info(f"Calculated target video bitrate: {target_bitrate_kbps} kbps")
        else:
            # Default conservative bitrate if we can't determine duration
            target_bitrate_kbps = 500
            logger.info(f"Using default video bitrate: {target_bitrate_kbps} kbps")
        
        # Audio bitrate: use 64kbps for compressed files
        audio_bitrate_kbps = 64
        
        logger.info(f"Compressing video: {input_path} -> {output_path}")
        
        # Use ffmpeg to compress the video
        # -c:v libx264: Use H.264 codec for video
        # -b:v: Set video bitrate
        # -preset fast: Balance between compression speed and efficiency
        # -c:a aac: Use AAC codec for audio
        # -b:a: Set audio bitrate
        # -movflags +faststart: Optimize for streaming
        # -y: Overwrite output file if it exists
        stream = ffmpeg.input(input_path)
        stream = ffmpeg.output(
            stream,
            output_path,
            **{
                'c:v': 'libx264',
                'b:v': f'{target_bitrate_kbps}k',
                'preset': 'fast',
                'c:a': 'aac',
                'b:a': f'{audio_bitrate_kbps}k',
                'movflags': '+faststart'
            }
        )
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        
        # Verify output file exists
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"Compressed file not created: {output_path}")
        
        compressed_size = os.path.getsize(output_path)
        logger.info(f"Compressed video size: {compressed_size / (1024 * 1024):.2f} MB")
        
        # Check if compression was successful
        if compressed_size > target_size_mb * 1024 * 1024:
            logger.warning(f"Compressed file ({compressed_size / (1024 * 1024):.2f} MB) still exceeds target ({target_size_mb} MB)")
            # Try a second pass with even more aggressive compression
            if compressed_size > target_size_mb * 1024 * 1024 * 1.2:  # More than 20% over target
                logger.info("Attempting second compression pass with more aggressive settings")
                # Calculate even more aggressive bitrate
                new_target_bitrate = int(target_bitrate_kbps * 0.6)  # 60% of previous bitrate
                new_target_bitrate = max(100, new_target_bitrate)  # But not less than 100kbps
                
                temp_output = output_path + ".tmp"
                stream = ffmpeg.input(input_path)
                stream = ffmpeg.output(
                    stream,
                    temp_output,
                    **{
                        'c:v': 'libx264',
                        'b:v': f'{new_target_bitrate}k',
                        'preset': 'fast',
                        'c:a': 'aac',
                        'b:a': '48k',  # Even lower audio bitrate
                        'movflags': '+faststart'
                    }
                )
                ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
                
                # Replace the first compressed file with the second pass
                if os.path.exists(temp_output):
                    os.replace(temp_output, output_path)
                    compressed_size = os.path.getsize(output_path)
                    logger.info(f"Second pass compressed video size: {compressed_size / (1024 * 1024):.2f} MB")
        
        return {
            'success': True,
            'filepath': output_path,
            'original_size': original_size,
            'compressed_size': compressed_size
        }
    
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error compressing video: {e.stderr.decode() if e.stderr else str(e)}")
        return {
            'success': False,
            'error': f"FFmpeg error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Error compressing video: {e}")
        return {
            'success': False,
            'error': str(e)
        }
