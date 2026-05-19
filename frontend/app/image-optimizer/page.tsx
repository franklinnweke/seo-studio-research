import { AppShell } from "@/components/app-shell";
import { ImageUploadPanel } from "@/components/image-upload-panel";

export default function ImageOptimizerPage() {
  return (
    <AppShell
      active="image-optimizer"
      title="Image Optimizer"
      subtitle="Upload, compress, convert, and download optimized image files."
    >
      <ImageUploadPanel />
    </AppShell>
  );
}
