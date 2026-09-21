import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatKickoff, formatStake } from "../format";
import type { BankrollPoint } from "../types";
import styles from "./BankrollChart.module.css";

const ACCENT = "#4d8dff";
const BORDER = "#262832";
const TEXT_DIM = "#7d818d";

interface BankrollChartProps {
  points: BankrollPoint[];
  initialBalance: number;
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: BankrollPoint }[];
}) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0].payload;
  return (
    <div className={styles.tooltip}>
      <div>{point.label}</div>
      <div className="num">{formatStake(point.balance)}</div>
      <div className={styles.tooltipDate}>{formatKickoff(point.at)}</div>
    </div>
  );
}

export function BankrollChart({ points, initialBalance }: BankrollChartProps) {
  if (points.length <= 1) {
    return <div className={styles.empty}>Pas encore assez de paris réglés pour une courbe.</div>;
  }

  const data = points.map((p, index) => ({ ...p, index }));

  return (
    <div className={styles.wrapper}>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="bankrollFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={ACCENT} stopOpacity={0.25} />
              <stop offset="100%" stopColor={ACCENT} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={BORDER} vertical={false} />
          <XAxis
            dataKey="index"
            tickFormatter={(index: number) => String(index)}
            stroke={TEXT_DIM}
            tick={{ fontSize: 11, fill: TEXT_DIM }}
            tickLine={false}
            axisLine={{ stroke: BORDER }}
            label={{ value: "Paris réglés", position: "insideBottom", offset: -2, fontSize: 11, fill: TEXT_DIM }}
          />
          <YAxis
            stroke={TEXT_DIM}
            tick={{ fontSize: 11, fill: TEXT_DIM }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => formatStake(v)}
            width={64}
            domain={([dataMin, dataMax]: readonly [number, number]) => {
              const lowest = Math.min(dataMin, initialBalance);
              const highest = Math.max(dataMax, initialBalance);
              const pad = Math.max((highest - lowest) * 0.1, 1);
              return [lowest - pad, highest + pad];
            }}
            allowDecimals={false}
          />
          <ReferenceLine
            y={initialBalance}
            stroke={TEXT_DIM}
            strokeDasharray="3 3"
            label={{ value: "Départ", position: "insideTopLeft", fontSize: 11, fill: TEXT_DIM }}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: TEXT_DIM, strokeDasharray: "3 3" }} />
          <Area
            type="monotone"
            dataKey="balance"
            stroke={ACCENT}
            strokeWidth={2}
            fill="url(#bankrollFill)"
            activeDot={{ r: 4, fill: ACCENT, stroke: "none" }}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
