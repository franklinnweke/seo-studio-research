import { AppShell } from "@/components/app-shell";
import { ImageResizerPanel } from "@/components/image-resizer-panel";

export default function ImageResizerPage() {
  return (
    <AppShell
      active="image-resizer"
      title="Image Resizer"
      subtitle="Resize, crop, convert, and review focal-point crops for website image sizes."
      sidebarPhase="Phase 8 active"
      sidebarDescription="Resize images into fixed website dimensions with crop review before processing."
    >
      <ImageResizerPanel />
    </AppShell>
  );
}
