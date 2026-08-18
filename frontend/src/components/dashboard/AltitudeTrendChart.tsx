import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface AltitudeTrendChartProps {
  trendData?: Array<{ day: string; altitudeKm: number }>;
}

export function AltitudeTrendChart({ trendData }: AltitudeTrendChartProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          Fleet Average Altitude — 14 Day Trend
        </CardTitle>
      </CardHeader>
      <CardContent className="h-56 pl-0">
        {!trendData || trendData.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            No trend data available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trendData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="altitudeFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(178 58% 51%)" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="hsl(178 58% 51%)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="day"
                stroke="hsl(220 20% 65%)"
                fontSize={11}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                stroke="hsl(220 20% 65%)"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                domain={["dataMin - 10", "dataMax + 10"]}
                width={48}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(222 45% 12%)",
                  border: "1px solid hsl(217 36% 21%)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelStyle={{ color: "hsl(220 33% 93%)" }}
                formatter={(value: number) => [`${value} km`, "Avg. altitude"]}
              />
              <Area
                type="monotone"
                dataKey="altitudeKm"
                stroke="hsl(178 58% 51%)"
                strokeWidth={2}
                fill="url(#altitudeFill)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
