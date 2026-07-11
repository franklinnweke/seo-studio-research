"use client";

import { useEffect, useState } from "react";

import { getApiFileObjectUrl } from "@/lib/api";

export function useAuthenticatedObjectUrl(url: string) {
  const [objectUrl, setObjectUrl] = useState("");

  useEffect(() => {
    if (!url) {
      return;
    }

    let revoked = false;
    let nextObjectUrl = "";

    getApiFileObjectUrl(url)
      .then((blobUrl) => {
        if (revoked) {
          window.URL.revokeObjectURL(blobUrl);
          return;
        }
        nextObjectUrl = blobUrl;
        setObjectUrl(blobUrl);
      })
      .catch(() => setObjectUrl(""));

    return () => {
      revoked = true;
      if (nextObjectUrl) {
        window.URL.revokeObjectURL(nextObjectUrl);
      }
    };
  }, [url]);

  return url ? objectUrl : "";
}
