import { CatalogTable } from "@/components/satellites/CatalogTable";

export function AllSatellitesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Global Space Catalog</h1>
        <p className="text-sm text-muted-foreground">
          Comprehensive catalog of orbital objects. Search and track objects to include them in your fleet's conjunction screening.
        </p>
      </div>

      <CatalogTable />
    </div>
  );
}

