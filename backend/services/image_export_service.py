from pathlib import Path
from typing import Optional, Dict, Any
from PIL import Image
import logging

from ..utils.image_utils import ImageUtils

logger = logging.getLogger(__name__)


class ImageExportService:
    """
    Service for exporting and managing ticket images
    """
    
    def __init__(self, base_path: str = "/data/batches"):
        self.base_path = Path(base_path)
        self.image_utils = ImageUtils()
        
        # Export settings
        self.default_format = "PNG"
        self.default_quality = 95
        self.optimize_images = True
        
        # Ensure base directory exists
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create base directory {self.base_path}: {e}")
    
    def save_ticket_image(self, image: Image.Image, batch_id: str, 
                         ticket_number: Optional[str], page_number: int) -> Dict[str, Any]:
        """
        Save ticket image to the batch directory
        
        Args:
            image: PIL Image to save
            batch_id: Batch identifier
            ticket_number: Ticket number (if detected)
            page_number: PDF page number
            
        Returns:
            Dictionary with save results:
            {
                'success': bool,
                'image_path': str,
                'filename': str,
                'file_size_bytes': int,
                'error': Optional[str]
            }
        """
        result = {
            'success': False,
            'image_path': '',
            'filename': '',
            'file_size_bytes': 0,
            'error': None
        }
        
        try:
            # Create batch image directory
            batch_images_dir = self._get_batch_images_directory(batch_id)
            
            # Generate filename
            filename = self.image_utils.generate_image_filename(ticket_number, page_number)
            image_path = batch_images_dir / filename
            
            # Ensure unique filename if file already exists
            image_path = self._ensure_unique_filename(image_path)
            
            # Save the image
            success = self.image_utils.save_image_as_png(
                image, 
                image_path, 
                optimize=self.optimize_images,
                quality=self.default_quality
            )
            
            if success and image_path.exists():
                file_size = image_path.stat().st_size
                
                result.update({
                    'success': True,
                    'image_path': str(image_path),
                    'filename': image_path.name,
                    'file_size_bytes': file_size
                })
                
                logger.info(f"Successfully saved ticket image: {image_path} ({file_size} bytes)")
            else:
                result['error'] = "Failed to save image file"
                logger.error(f"Failed to save image: {image_path}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error saving ticket image: {e}"
            logger.error(error_msg)
            result['error'] = error_msg
            return result
    
    def _get_batch_images_directory(self, batch_id: str) -> Path:
        """
        Get or create the images directory for a batch
        
        Args:
            batch_id: Batch identifier
            
        Returns:
            Path to the batch images directory
        """
        batch_dir = self.base_path / str(batch_id)
        images_dir = batch_dir / "images"
        
        # Create directory if it doesn't exist
        images_dir.mkdir(parents=True, exist_ok=True)
        
        return images_dir
    
    def _ensure_unique_filename(self, image_path: Path) -> Path:
        """
        Ensure filename is unique by adding suffix if necessary
        
        Args:
            image_path: Original path
            
        Returns:
            Unique path
        """
        if not image_path.exists():
            return image_path
        
        # Add numeric suffix to make unique
        counter = 1
        base_path = image_path.parent
        stem = image_path.stem
        suffix = image_path.suffix
        
        while True:
            new_path = base_path / f"{stem}_{counter}{suffix}"
            if not new_path.exists():
                return new_path
            counter += 1
            
            # Safety check to avoid infinite loop
            if counter > 1000:
                logger.warning(f"Too many files with similar names: {stem}")
                return image_path
    
    def get_image_path(self, batch_id: str, filename: str) -> Optional[Path]:
        """
        Get the full path to a saved image
        
        Args:
            batch_id: Batch identifier
            filename: Image filename
            
        Returns:
            Path to the image or None if not found
        """
        try:
            images_dir = self._get_batch_images_directory(batch_id)
            image_path = images_dir / filename
            
            if image_path.exists():
                return image_path
            else:
                logger.warning(f"Image not found: {image_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting image path: {e}")
            return None
    
    def delete_image(self, batch_id: str, filename: str) -> bool:
        """
        Delete a saved image file
        
        Args:
            batch_id: Batch identifier
            filename: Image filename
            
        Returns:
            True if successfully deleted
        """
        try:
            image_path = self.get_image_path(batch_id, filename)
            
            if image_path and image_path.exists():
                image_path.unlink()
                logger.info(f"Deleted image: {image_path}")
                return True
            else:
                logger.warning(f"Image not found for deletion: {batch_id}/{filename}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting image: {e}")
            return False
    
    def list_batch_images(self, batch_id: str) -> list[Dict[str, Any]]:
        """
        List all images in a batch directory
        
        Args:
            batch_id: Batch identifier
            
        Returns:
            List of image info dictionaries
        """
        try:
            images_dir = self._get_batch_images_directory(batch_id)
            
            if not images_dir.exists():
                return []
            
            images = []
            for image_path in images_dir.glob("*.png"):
                try:
                    stat = image_path.stat()
                    images.append({
                        'filename': image_path.name,
                        'path': str(image_path),
                        'size_bytes': stat.st_size,
                        'created_at': stat.st_ctime,
                        'modified_at': stat.st_mtime
                    })
                except Exception as e:
                    logger.warning(f"Error reading image file info {image_path}: {e}")
                    continue
            
            # Sort by creation time
            images.sort(key=lambda x: x['created_at'])
            
            return images
            
        except Exception as e:
            logger.error(f"Error listing batch images: {e}")
            return []
    
    def get_batch_images_info(self, batch_id: str) -> Dict[str, Any]:
        """
        Get summary information about images in a batch
        
        Args:
            batch_id: Batch identifier
            
        Returns:
            Dictionary with batch images information
        """
        try:
            images = self.list_batch_images(batch_id)
            
            total_size = sum(img['size_bytes'] for img in images)
            
            return {
                'batch_id': batch_id,
                'image_count': len(images),
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024),
                'images': images
            }
            
        except Exception as e:
            logger.error(f"Error getting batch images info: {e}")
            return {
                'batch_id': batch_id,
                'image_count': 0,
                'total_size_bytes': 0,
                'total_size_mb': 0.0,
                'images': [],
                'error': str(e)
            }
    
    def cleanup_batch_images(self, batch_id: str) -> Dict[str, Any]:
        """
        Clean up all images in a batch directory
        
        Args:
            batch_id: Batch identifier
            
        Returns:
            Dictionary with cleanup results
        """
        result = {
            'success': False,
            'deleted_count': 0,
            'errors': []
        }
        
        try:
            images = self.list_batch_images(batch_id)
            
            for image_info in images:
                try:
                    image_path = Path(image_info['path'])
                    if image_path.exists():
                        image_path.unlink()
                        result['deleted_count'] += 1
                except Exception as e:
                    error_msg = f"Failed to delete {image_info['filename']}: {e}"
                    result['errors'].append(error_msg)
                    logger.error(error_msg)
            
            result['success'] = len(result['errors']) == 0
            
            logger.info(f"Cleanup batch {batch_id}: deleted {result['deleted_count']} images, "
                       f"{len(result['errors'])} errors")
            
            return result
            
        except Exception as e:
            error_msg = f"Error during batch cleanup: {e}"
            logger.error(error_msg)
            result['errors'].append(error_msg)
            return result
    
    def verify_image_integrity(self, batch_id: str, filename: str) -> bool:
        """
        Verify that a saved image can be opened and is valid
        
        Args:
            batch_id: Batch identifier
            filename: Image filename
            
        Returns:
            True if image is valid
        """
        try:
            image_path = self.get_image_path(batch_id, filename)
            
            if not image_path or not image_path.exists():
                return False
            
            # Try to open the image
            with Image.open(image_path) as img:
                # Verify image can be loaded
                img.load()
                
                # Basic checks
                if img.size[0] <= 0 or img.size[1] <= 0:
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Image integrity check failed for {batch_id}/{filename}: {e}")
            return False
    
    def get_export_statistics(self) -> Dict[str, Any]:
        """
        Get overall export statistics across all batches
        
        Returns:
            Dictionary with export statistics
        """
        try:
            stats = {
                'total_batches': 0,
                'total_images': 0,
                'total_size_bytes': 0,
                'total_size_mb': 0.0,
                'batch_details': []
            }
            
            # Scan all batch directories
            if self.base_path.exists():
                for batch_dir in self.base_path.iterdir():
                    if batch_dir.is_dir():
                        batch_info = self.get_batch_images_info(batch_dir.name)
                        
                        if batch_info['image_count'] > 0:
                            stats['total_batches'] += 1
                            stats['total_images'] += batch_info['image_count']
                            stats['total_size_bytes'] += batch_info['total_size_bytes']
                            stats['batch_details'].append(batch_info)
                
                stats['total_size_mb'] = stats['total_size_bytes'] / (1024 * 1024)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting export statistics: {e}")
            return {
                'total_batches': 0,
                'total_images': 0,
                'total_size_bytes': 0,
                'total_size_mb': 0.0,
                'batch_details': [],
                'error': str(e)
            }