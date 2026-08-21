import { format, parseISO } from "date-fns";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceArea,
  TooltipProps
} from "recharts";

import { useConjunctions } from "@/hooks/useConjunctions";

const RISK_COLORS: Record<string, string> = {
  critical: "#ef4444", // red-500
  high: "#f97316", // orange-500
  medium: "#eab308", // yellow-500
  low: "#64748b", // slate-500
};

export function TimelineChart() {
  const { conjunctions, isLoading } = useConjunctions();

  if (isLoading) {
    return <div className="h-[400px] flex items-center justify-center text-slate-500">Loading timeline...</div>;
  }

  if (conjunctions.length === 0) {
    return <div className="h-[400px] flex items-center justify-center text-slate-500 border border-dashed rounded-md m-4">No events to display.</div>;
  }

  // Map to format required by Recharts
  const data = conjunctions.map((c) => ({
    ...c,
    tcaTimestamp: parseISO(c.tca).getTime(),
    bubbleSize: Math.max(Math.log10(Math.max(c.probability, 1e-8)) + 8, 1) * 200, // scaled for visualization
  }));

  const minTime = Math.min(...data.map((d) => d.tcaTimestamp));
  const maxTime = Math.max(...data.map((d) => d.tcaTimestamp));

  // Add 10% padding to X axis domain
  const timePadding = (maxTime - minTime) * 0.1;
  const domainX = [minTime - timePadding, maxTime + timePadding];

  const CustomTooltip = ({ active, payload }: TooltipProps<number, string>) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-3 rounded-md shadow-md text-sm">
          <p className="font-bold mb-1">{data.primarySatelliteName} vs {data.secondarySatelliteName}</p>
          <p><span className="text-slate-500">TCA:</span> {format(data.tcaTimestamp, "yyyy-MM-dd HH:mm:ss")}</p>
          <p><span className="text-slate-500">Miss Dist:</span> {data.missDistanceKm.toFixed(2)} km</p>
          <p><span className="text-slate-500">Probability:</span> {data.probability.toExponential(2)}</p>
          <p><span className="text-slate-500">Risk:</span> <span style={{color: RISK_COLORS[data.riskLevel] || RISK_COLORS.low}} className="uppercase font-semibold">{data.riskLevel}</span></p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="h-[400px] w-full p-4 border border-slate-200 dark:border-slate-800 rounded-md bg-white dark:bg-slate-950">
      <h3 className="font-semibold text-slate-900 dark:text-white mb-4">Risk Timeline Overview</h3>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} vertical={false} />
          
          <XAxis 
            type="number" 
            dataKey="tcaTimestamp" 
            name="Time of Closest Approach" 
            domain={domainX}
            tickFormatter={(unixTime) => format(unixTime, "MM/dd HH:mm")}
            tick={{ fill: "#64748b", fontSize: 12 }}
            tickMargin={10}
          />
          
          <YAxis 
            type="number" 
            dataKey="missDistanceKm" 
            name="Miss Distance (km)" 
            unit=" km"
            tick={{ fill: "#64748b", fontSize: 12 }}
          />
          
          <ZAxis type="number" dataKey="bubbleSize" range={[50, 800]} />
          
          <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />
          
          {/* Highlight risk zones under 5km */}
          <ReferenceArea y1={0} y2={1} fill="#ef4444" fillOpacity={0.05} />
          <ReferenceArea y1={1} y2={5} fill="#f97316" fillOpacity={0.05} />

          <Scatter name="Conjunctions" data={data}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={RISK_COLORS[entry.riskLevel] || RISK_COLORS.low} opacity={0.8} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
