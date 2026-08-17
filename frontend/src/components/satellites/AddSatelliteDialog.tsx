import { useState, type FormEvent } from "react";
import { Loader2, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/apiClient";

/**
 * UI-only for now — wire onSubmit to
 * POST /api/v1/satellites { norad_id } once that endpoint is available.
 */
export function AddSatelliteDialog() {
  const [open, setOpen] = useState(false);
  const [noradId, setNoradId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    
    try {
      await apiClient.post("/satellites/norad", { norad_id: Number(noradId) });
      setOpen(false);
      setNoradId("");
      // Quickest way to sync state across sibling components without context/SWR
      window.location.reload();
    } catch (error) {
      console.error("Failed to add satellite:", error);
      // Ideally we would show a toast here
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="mr-2 h-4 w-4" />
          Add Satellite
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add satellite by NORAD ID</DialogTitle>
          <DialogDescription>
            Fetches the latest TLE / OMM from CelesTrak and begins tracking.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="norad_id">NORAD Catalog ID</Label>
            <Input
              id="norad_id"
              placeholder="25544"
              inputMode="numeric"
              value={noradId}
              onChange={(e) => setNoradId(e.target.value)}
              required
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={isSubmitting || !noradId}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Track satellite
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
