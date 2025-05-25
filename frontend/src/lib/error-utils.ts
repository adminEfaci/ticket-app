export function getErrorMessage(error: any): string {
  // Handle axios error responses
  if (error.response?.data?.detail) {
    const detail = error.response.data.detail;
    
    // Handle structured error responses (like upload responses)
    if (typeof detail === 'object' && !Array.isArray(detail)) {
      if (detail.message) {
        // If there are failed batches, append their errors
        if (detail.failed_batches && detail.failed_batches.length > 0) {
          const errors = detail.failed_batches.map((batch: any) => batch.error).join('; ');
          return `${detail.message}. Errors: ${errors}`;
        }
        return detail.message;
      }
      if (detail.msg) {
        return detail.msg;
      }
    }
    
    // If detail is an array of validation errors
    if (Array.isArray(detail)) {
      return detail.map((err: any) => {
        if (typeof err === 'string') return err;
        if (err.msg) return err.msg;
        if (err.message) return err.message;
        return 'Validation error';
      }).join(', ');
    }
    
    // If detail is a string
    if (typeof detail === 'string') {
      return detail;
    }
  }
  
  // Fallback error messages
  if (error.message) return error.message;
  if (typeof error === 'string') return error;
  
  return 'An unexpected error occurred';
}