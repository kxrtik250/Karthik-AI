import { useState, useEffect, useCallback, useRef } from "react";
import {
  listDocuments,
  uploadDocument as apiUploadDocument,
  deleteDocument as apiDeleteDocument,
} from "../api/documents";

export function useDocuments() {
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isDeletingId, setIsDeletingId] = useState(null);
  const [error, setError] = useState(null);

  const pollingTimerRef = useRef(null);

  const loadDocuments = useCallback(async () => {
    try {
      const data = await listDocuments();
      setDocuments(data || []);
      setError(null);
    } catch (err) {
      setError(err.message || "Failed to load documents");
    }
  }, []);

  // Initial load
  useEffect(() => {
    setIsLoading(true);
    loadDocuments().finally(() => setIsLoading(false));
  }, [loadDocuments]);

  // Polling effect: if any document has status 'processing' or 'pending', poll every 2s
  useEffect(() => {
    const hasProcessing = documents.some(
      (d) => d.status === "processing" || d.status === "pending"
    );

    if (hasProcessing) {
      pollingTimerRef.current = setTimeout(() => {
        loadDocuments();
      }, 2000);
    }

    return () => {
      if (pollingTimerRef.current) {
        clearTimeout(pollingTimerRef.current);
      }
    };
  }, [documents, loadDocuments]);

  const uploadFile = useCallback(
    async (file) => {
      try {
        setIsUploading(true);
        setError(null);
        const newDoc = await apiUploadDocument(file);
        // Prepend to document list
        setDocuments((prev) => [newDoc, ...prev]);
        // Trigger immediate status check
        await loadDocuments();
      } catch (err) {
        setError(err.message || "Failed to upload document");
      } finally {
        setIsUploading(false);
      }
    },
    [loadDocuments]
  );

  const deleteDocument = useCallback(async (id) => {
    try {
      setIsDeletingId(id);
      await apiDeleteDocument(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
      setError(null);
    } catch (err) {
      setError(err.message || "Failed to delete document");
    } finally {
      setIsDeletingId(null);
    }
  }, []);

  return {
    documents,
    isLoading,
    isUploading,
    isDeletingId,
    error,
    uploadFile,
    deleteDocument,
    refreshDocuments: loadDocuments,
    clearError: () => setError(null),
  };
}
