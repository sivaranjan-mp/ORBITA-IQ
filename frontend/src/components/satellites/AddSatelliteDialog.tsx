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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { apiClient } from "@/lib/apiClient";

export function AddSatelliteDialog() {
  const [open, setOpen] = useState(false);
  const [noradId, setNoradId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // Bulk state
  const [bulkNoradIds, setBulkNoradIds] = useState("");
  const [bulkResults, setBulkResults] = useState<{ norad_id: number, success: boolean, reason?: string }[] | null>(null);

  // Reset state when dialog opens/closes
  const handleOpenChange = (newOpen: boolean) => {
    setOpen(newOpen);
    if (!newOpen) {
      setNoradId("");
      setBulkNoradIds("");
      setBulkResults(null);
    }
  };

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    
    try {
      await apiClient.post("/satellites/norad", { norad_id: Number(noradId) });
      setOpen(false);
      setNoradId("");
      window.location.reload();
    } catch (error) {
      console.error("Failed to add satellite:", error);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleBulkSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    
    try {
      // Split by newline, comma, or space
      const ids = bulkNoradIds
        .split(/[\n, ]+/)
        .map(id => id.trim())
        .filter(id => id.length > 0)
        .map(Number)
        .filter(id => !isNaN(id));
      
      if (ids.length === 0) {
        alert("Please enter at least one valid numeric NORAD ID.");
        setIsSubmitting(false);
        return;
      }

      const response = await apiClient.post("/satellites/norad/bulk", { norad_ids: ids });
      setBulkResults(response.data.results);
    } catch (error) {
      console.error("Failed to bulk add satellites:", error);
      alert("An error occurred while tracking satellites. Check the console for details.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="mr-2 h-4 w-4" />
          Add Satellite
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Satellite(s)</DialogTitle>
          <DialogDescription>
            Fetch the latest TLE / OMM from CelesTrak and begin tracking.
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="single">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="single">Single</TabsTrigger>
            <TabsTrigger value="bulk">Bulk (Multiple)</TabsTrigger>
          </TabsList>

          <TabsContent value="single">
            <form onSubmit={handleSubmit} className="space-y-4 pt-4">
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
          </TabsContent>

          <TabsContent value="bulk">
            <form onSubmit={handleBulkSubmit} className="space-y-4 pt-4">
              <div className="space-y-2">
                <Label htmlFor="bulk_norad_ids">NORAD Catalog IDs (one per line)</Label>
                <Textarea
                  id="bulk_norad_ids"
                  placeholder={"25544\n20580"}
                  value={bulkNoradIds}
                  onChange={(e) => setBulkNoradIds(e.target.value)}
                  required
                  rows={5}
                />
              </div>

              {bulkResults && (
                <div className="space-y-2 max-h-48 overflow-y-auto rounded bg-muted p-2 text-sm">
                  <div className="font-medium text-foreground mb-2">Results Summary:</div>
                  {bulkResults.map((res, i) => (
                    <div key={i} className={`flex justify-between ${res.success ? "text-green-600" : "text-destructive"}`}>
                      <span className="font-medium">{res.norad_id}:</span>
                      <span>{res.success ? "Added successfully" : res.reason || "Failed"}</span>
                    </div>
                  ))}
                </div>
              )}

              <DialogFooter>
                {bulkResults ? (
                  <Button type="button" onClick={() => window.location.reload()}>
                    Close & Refresh
                  </Button>
                ) : (
                  <Button type="submit" disabled={isSubmitting || !bulkNoradIds.trim()}>
                    {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Track satellites
                  </Button>
                )}
              </DialogFooter>
            </form>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
