import type { CSSProperties, ReactNode } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  LabelList,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

export type HorizonEvDatum = {
  horizon: string | number;
  expectedReturn: number;
  pProfit?: number | null;
};

export type ForecastFanDatum = {
  step: string | number;
  p5?: number | null;
  p50?: number | null;
  p95?: number | null;
};

export type SpreadLiquidityDatum = {
  label?: string;
  spreadPct: number;
  liquidity: number;
  ev?: number | null;
};

export type BacktestCurveDatum = {
  step: string | number;
  equity: number;
  drawdown: number;
};

export type CalibrationBinDatum = {
  bin: string | number;
  predicted: number;
  observed: number;
  count?: number | null;
};

export type EdgeDecayDatum = {
  ageMinutes: number;
  edge: number;
  fillProbability?: number | null;
};

type ChartShellProps = {
  title: string;
  description: string;
  height?: number;
  children: ReactNode;
};

type BaseChartProps = {
  title?: string;
  description?: string;
  height?: number;
};

type TooltipValue = string | number | readonly (string | number)[] | undefined;

const chartShellStyle: CSSProperties = {
  minWidth: 0,
  width: "100%",
};

const chartHeaderStyle: CSSProperties = {
  display: "grid",
  gap: 4,
  marginBottom: 8,
};

const titleStyle: CSSProperties = {
  margin: 0,
  color: "var(--text, #f4f7f5)",
  fontSize: "0.9rem",
  fontWeight: 600,
  letterSpacing: 0,
};

const descriptionStyle: CSSProperties = {
  margin: 0,
  color: "var(--muted, #9ca3af)",
  fontSize: "0.74rem",
  lineHeight: 1.45,
};

const emptyStyle: CSSProperties = {
  display: "grid",
  minHeight: 140,
  placeItems: "center",
  border: "1px dashed var(--line, rgba(63, 63, 70, 0.58))",
  borderRadius: 6,
  color: "var(--muted, #9ca3af)",
  fontSize: "0.78rem",
};

const gridStyle: CSSProperties = {
  display: "grid",
  gap: 16,
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))",
};

const mobileSafeMargin = { top: 12, right: 14, left: 0, bottom: 12 };
const gridStroke = "rgba(63,63,70,0.28)";
const axisTick = { fill: "var(--muted, #9ca3af)", fontSize: 11 };
const tooltipStyle = {
  background: "#0a0e10",
  border: "1px solid rgba(63,63,70,0.6)",
  color: "#f4f7f5",
};

function idFromTitle(title: string) {
  return title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function pct(value: unknown, digits = 1) {
  return isFiniteNumber(value) ? `${(value * 100).toFixed(digits)}%` : "-";
}

function compact(value: unknown) {
  if (!isFiniteNumber(value)) return "-";
  return Intl.NumberFormat("en-US", { maximumFractionDigits: 2, notation: "compact" }).format(value);
}

function signedPct(value: unknown, digits = 1) {
  if (!isFiniteNumber(value)) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${pct(value, digits)}`;
}

function ChartShell({ title, description, height = 220, children }: ChartShellProps) {
  const titleId = `${idFromTitle(title)}-title`;
  const descriptionId = `${idFromTitle(title)}-description`;

  return (
    <section style={chartShellStyle} role="img" aria-labelledby={titleId} aria-describedby={descriptionId}>
      <div style={chartHeaderStyle}>
        <h3 id={titleId} style={titleStyle}>{title}</h3>
        <p id={descriptionId} style={descriptionStyle}>{description}</p>
      </div>
      <ResponsiveContainer width="100%" height={height} minWidth={0}>
        {children}
      </ResponsiveContainer>
    </section>
  );
}

function EmptyChart({ title, description, height }: ChartShellProps) {
  return (
    <section style={chartShellStyle} role="img" aria-label={`${title}. ${description}`}>
      <div style={chartHeaderStyle}>
        <h3 style={titleStyle}>{title}</h3>
        <p style={descriptionStyle}>{description}</p>
      </div>
      <div style={{ ...emptyStyle, height }}>No chart data.</div>
    </section>
  );
}

export function HorizonEvBars({
  data,
  title = "Horizon EV",
  description = "Expected value by holding horizon, with a zero line and p-profit labels.",
  height,
}: BaseChartProps & { data: HorizonEvDatum[] }) {
  if (!data.length) return <EmptyChart title={title} description={description} height={height} children={null} />;

  const chartData = data.map((row) => ({
    ...row,
    horizonLabel: String(row.horizon),
    pProfitLabel: isFiniteNumber(row.pProfit) ? `p ${pct(row.pProfit, 0)}` : "",
  }));

  return (
    <ChartShell title={title} description={description} height={height}>
      <BarChart data={chartData} margin={mobileSafeMargin}>
        <CartesianGrid stroke={gridStroke} vertical={false} />
        <XAxis dataKey="horizonLabel" tick={axisTick} />
        <YAxis tick={axisTick} tickFormatter={(value) => signedPct(value, 0)} width={42} />
        <Tooltip contentStyle={tooltipStyle} formatter={(value: TooltipValue, name) => {
          const key = String(name);
          return [key === "expectedReturn" ? signedPct(value, 2) : String(value), key === "expectedReturn" ? "expected return" : key];
        }} />
        <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="3 3" />
        <Bar dataKey="expectedReturn" radius={[3, 3, 0, 0]} isAnimationActive={false}>
          <LabelList dataKey="pProfitLabel" position="top" fill="#cbd5e1" fontSize={10} />
          {chartData.map((entry, index) => (
            <Cell key={`${entry.horizonLabel}-${index}`} fill={entry.expectedReturn >= 0 ? "#10b981" : "#f43f5e"} />
          ))}
        </Bar>
      </BarChart>
    </ChartShell>
  );
}

export function ForecastFanChart({
  data,
  askPrice,
  title = "Forecast Cone",
  description = "Fan chart with p5 to p95 uncertainty band and p50 median forecast.",
  height = 240,
}: BaseChartProps & { data: ForecastFanDatum[]; askPrice?: number | null }) {
  if (!data.length) return <EmptyChart title={title} description={description} height={height} children={null} />;

  const chartData = data.map((row) => ({
    ...row,
    stepLabel: String(row.step),
    base: isFiniteNumber(row.p5) ? row.p5 : null,
    band: isFiniteNumber(row.p5) && isFiniteNumber(row.p95) ? row.p95 - row.p5 : null,
  }));

  return (
    <ChartShell title={title} description={description} height={height}>
      <ComposedChart data={chartData} margin={mobileSafeMargin}>
        <defs>
          <linearGradient id="analyticsFanBand" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.34} />
            <stop offset="100%" stopColor="#10b981" stopOpacity={0.1} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={gridStroke} vertical={false} />
        <XAxis dataKey="stepLabel" tick={axisTick} />
        <YAxis tick={axisTick} tickFormatter={compact} width={48} domain={["auto", "auto"]} />
        <Tooltip contentStyle={tooltipStyle} formatter={(value: TooltipValue, name) => {
          const key = String(name);
          if (key === "base" || key === "band") return ["", ""];
          return [compact(value), key];
        }} />
        {isFiniteNumber(askPrice) ? <ReferenceLine y={askPrice} stroke="#94a3b8" strokeDasharray="4 4" label={{ value: "ask", fill: "#94a3b8", fontSize: 10 }} /> : null}
        <Area type="monotone" dataKey="base" stackId="fan" stroke="transparent" fill="transparent" isAnimationActive={false} />
        <Area type="monotone" dataKey="band" stackId="fan" stroke="transparent" fill="url(#analyticsFanBand)" isAnimationActive={false} />
        <Line type="monotone" dataKey="p50" stroke="#34d399" strokeWidth={2} dot={false} isAnimationActive={false} />
        <Line type="monotone" dataKey="p95" stroke="#38bdf8" strokeWidth={1} strokeDasharray="2 4" dot={false} isAnimationActive={false} />
        <Line type="monotone" dataKey="p5" stroke="#fbbf24" strokeWidth={1} strokeDasharray="2 4" dot={false} isAnimationActive={false} />
      </ComposedChart>
    </ChartShell>
  );
}

export function SpreadLiquidityScatter({
  data,
  title = "Spread / Liquidity",
  description = "Scatter plot comparing spread cost against liquidity; point color reflects positive or negative EV.",
  height,
}: BaseChartProps & { data: SpreadLiquidityDatum[] }) {
  if (!data.length) return <EmptyChart title={title} description={description} height={height} children={null} />;

  return (
    <ChartShell title={title} description={description} height={height}>
      <ScatterChart margin={mobileSafeMargin}>
        <CartesianGrid stroke={gridStroke} />
        <XAxis type="number" dataKey="spreadPct" name="spread" tick={axisTick} tickFormatter={(value) => pct(value, 0)} width={42} />
        <YAxis type="number" dataKey="liquidity" name="liquidity" tick={axisTick} width={42} />
        <ZAxis type="number" dataKey="ev" range={[48, 140]} />
        <Tooltip
          contentStyle={tooltipStyle}
          cursor={{ strokeDasharray: "3 3" }}
          formatter={(value: TooltipValue, name) => {
            const key = String(name);
            if (key === "spread") return [pct(value, 2), key];
            if (key === "ev") return [signedPct(value, 2), key];
            return [String(value), key];
          }}
        />
        <ReferenceLine x={0} stroke="#94a3b8" strokeDasharray="3 3" />
        <Scatter name="cards" data={data} isAnimationActive={false}>
          {data.map((entry, index) => (
            <Cell key={`${entry.label ?? "point"}-${index}`} fill={(entry.ev ?? 0) >= 0 ? "#10b981" : "#f43f5e"} />
          ))}
        </Scatter>
      </ScatterChart>
    </ChartShell>
  );
}

export function BacktestEquityDrawdownChart({
  data,
  title = "Backtest Equity / Drawdown",
  description = "Equity curve over time with drawdown shown below the zero line.",
  height = 240,
}: BaseChartProps & { data: BacktestCurveDatum[] }) {
  if (!data.length) return <EmptyChart title={title} description={description} height={height} children={null} />;

  const chartData = data.map((row) => ({ ...row, stepLabel: String(row.step) }));

  return (
    <ChartShell title={title} description={description} height={height}>
      <ComposedChart data={chartData} margin={mobileSafeMargin}>
        <CartesianGrid stroke={gridStroke} vertical={false} />
        <XAxis dataKey="stepLabel" tick={axisTick} />
        <YAxis yAxisId="equity" tick={axisTick} tickFormatter={compact} width={48} />
        <YAxis yAxisId="drawdown" orientation="right" tick={axisTick} tickFormatter={(value) => pct(value, 0)} width={42} />
        <Tooltip contentStyle={tooltipStyle} formatter={(value: TooltipValue, name) => {
          const key = String(name);
          return [key === "drawdown" ? pct(value, 2) : compact(value), key];
        }} />
        <Legend wrapperStyle={{ color: "#cbd5e1", fontSize: 11 }} />
        <ReferenceLine yAxisId="drawdown" y={0} stroke="#94a3b8" strokeDasharray="3 3" />
        <Area yAxisId="drawdown" type="monotone" dataKey="drawdown" stroke="#f43f5e" fill="#f43f5e" fillOpacity={0.18} dot={false} isAnimationActive={false} />
        <Line yAxisId="equity" type="monotone" dataKey="equity" stroke="#34d399" strokeWidth={2} dot={false} isAnimationActive={false} />
      </ComposedChart>
    </ChartShell>
  );
}

export function CalibrationReliabilityPlot({
  data,
  title = "Calibration Reliability",
  description = "Predicted probability versus observed frequency, with a diagonal perfect-calibration reference.",
  height,
}: BaseChartProps & { data: CalibrationBinDatum[] }) {
  if (!data.length) return <EmptyChart title={title} description={description} height={height} children={null} />;

  const reference = [
    { predicted: 0, observed: 0 },
    { predicted: 1, observed: 1 },
  ];

  return (
    <ChartShell title={title} description={description} height={height}>
      <ScatterChart margin={mobileSafeMargin}>
        <CartesianGrid stroke={gridStroke} />
        <XAxis type="number" dataKey="predicted" name="predicted" domain={[0, 1]} tick={axisTick} tickFormatter={(value) => pct(value, 0)} width={42} />
        <YAxis type="number" dataKey="observed" name="observed" domain={[0, 1]} tick={axisTick} tickFormatter={(value) => pct(value, 0)} width={42} />
        <ZAxis type="number" dataKey="count" range={[48, 150]} />
        <Tooltip contentStyle={tooltipStyle} formatter={(value: TooltipValue, name) => {
          const key = String(name);
          return [key === "predicted" || key === "observed" ? pct(value, 1) : String(value), key];
        }} />
        <Scatter name="perfect" data={reference} line={{ stroke: "#94a3b8", strokeDasharray: "4 4" }} fill="transparent" shape={() => null} isAnimationActive={false} />
        <Scatter name="bins" data={data} fill="#38bdf8" isAnimationActive={false} />
      </ScatterChart>
    </ChartShell>
  );
}

export function ExecutionEdgeDecayChart({
  data,
  title = "Execution Edge Decay",
  description = "Signal edge after listing age, with fill probability available as a secondary curve.",
  height,
}: BaseChartProps & { data: EdgeDecayDatum[] }) {
  if (!data.length) return <EmptyChart title={title} description={description} height={height} children={null} />;

  const hasFillProbability = data.some((row) => isFiniteNumber(row.fillProbability));

  return (
    <ChartShell title={title} description={description} height={height}>
      <ComposedChart data={data} margin={mobileSafeMargin}>
        <CartesianGrid stroke={gridStroke} vertical={false} />
        <XAxis dataKey="ageMinutes" tick={axisTick} tickFormatter={(value) => `${value}m`} />
        <YAxis yAxisId="edge" tick={axisTick} tickFormatter={(value) => signedPct(value, 0)} width={42} />
        {hasFillProbability ? <YAxis yAxisId="fill" orientation="right" tick={axisTick} tickFormatter={(value) => pct(value, 0)} width={42} /> : null}
        <Tooltip contentStyle={tooltipStyle} formatter={(value: TooltipValue, name) => {
          const key = String(name);
          return [key === "fillProbability" ? pct(value, 1) : signedPct(value, 2), key === "fillProbability" ? "fill probability" : "edge"];
        }} />
        <ReferenceLine yAxisId="edge" y={0} stroke="#94a3b8" strokeDasharray="3 3" />
        <Area yAxisId="edge" type="monotone" dataKey="edge" stroke="#10b981" fill="#10b981" fillOpacity={0.18} dot={false} isAnimationActive={false} />
        {hasFillProbability ? <Line yAxisId="fill" type="monotone" dataKey="fillProbability" stroke="#38bdf8" strokeWidth={2} dot={false} isAnimationActive={false} /> : null}
      </ComposedChart>
    </ChartShell>
  );
}

export type AnalyticsCharts2DProps = {
  horizonEv?: HorizonEvDatum[];
  forecastFan?: ForecastFanDatum[];
  forecastAskPrice?: number | null;
  spreadLiquidity?: SpreadLiquidityDatum[];
  backtest?: BacktestCurveDatum[];
  calibration?: CalibrationBinDatum[];
  edgeDecay?: EdgeDecayDatum[];
};

export function AnalyticsCharts2D({
  horizonEv = [],
  forecastFan = [],
  forecastAskPrice,
  spreadLiquidity = [],
  backtest = [],
  calibration = [],
  edgeDecay = [],
}: AnalyticsCharts2DProps) {
  return (
    <div style={gridStyle}>
      <HorizonEvBars data={horizonEv} />
      <ForecastFanChart data={forecastFan} askPrice={forecastAskPrice} />
      <SpreadLiquidityScatter data={spreadLiquidity} />
      <BacktestEquityDrawdownChart data={backtest} />
      <CalibrationReliabilityPlot data={calibration} />
      <ExecutionEdgeDecayChart data={edgeDecay} />
    </div>
  );
}

export default AnalyticsCharts2D;
