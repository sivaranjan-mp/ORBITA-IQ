interface ProbabilityGaugeProps {
  probability: number;
  size?: number;
}

export const ProbabilityGauge: React.FC<ProbabilityGaugeProps> = ({ probability, size = 120 }) => {
  // Convert probability to a 0-100 scale logarithmically
  // Let's say: 1e-6 is 0%, 1e-3 is 50%, 1 is 100%
  const minLog = -6;
  const maxLog = 0;
  const p = Math.max(probability, 1e-7); // clamp to avoid log(0)
  const logP = Math.log10(p);
  const percentage = Math.max(0, Math.min(100, ((logP - minLog) / (maxLog - minLog)) * 100));

  const strokeWidth = 10;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;

  let color = "text-green-500";
  if (probability >= 1e-4) color = "text-red-500";
  else if (probability >= 1e-5) color = "text-orange-500";
  else if (probability >= 1e-6) color = "text-yellow-500";

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        {/* Background Circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          className="text-gray-200 dark:text-gray-700"
          strokeWidth={strokeWidth}
          stroke="currentColor"
          fill="transparent"
        />
        {/* Progress Circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          className={`${color} transition-all duration-1000 ease-out`}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          stroke="currentColor"
          fill="transparent"
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center">
        <span className="text-sm font-bold text-slate-800 dark:text-slate-100">
          {probability.toExponential(2)}
        </span>
        <span className="text-[10px] text-slate-500 uppercase font-semibold tracking-wider">
          Pc
        </span>
      </div>
    </div>
  );
};
