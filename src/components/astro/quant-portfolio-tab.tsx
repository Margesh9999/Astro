'use client';

import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts';
import { quantDeskApi } from '@/lib/astro/api-quant';
import {
  AXIS_TICK, C, ChartTitle, HeatGrid, InsightBox, LoadState, SectionTitle, TIP_STYLE, divergeStyle, fmtSigned, signColor, useQuant,
} from './quant-ui';

const PALETTE = ['#b0763a', '#4fa8a0', '#9b8ac4', '#d96f85', '#6fa96f', '#c98a2e', '#7a8fb8'];
const SHORT: Record<string, string> = {
  'Equal weight': 'Equal',
  'Inverse volatility': 'Inv-vol',
  'Minimum variance': 'Min-var',
  'Maximum Sharpe': 'Max-Sharpe',
  'Risk parity (ERC)': 'Risk parity',
  'Hierarchical Risk Parity': 'HRP',
};

export function QuantPortfolioTab({ symbol }: { symbol: string }) {
  const { data, error, loading } = useQuant(symbol, quantDeskApi.portfolio);
  if (!data) return <LoadState loading={loading} error={error} what="Portfolio optimiser" />;
  const weightRows = data.portfolios.map((p) => {
    const row: Record<string, number | string> = { name: SHORT[p.name] ?? p.name };
    data.assets.forEach((a, i) => (row[a] = p.weights[i]));
    return row;
  });
  const portPts = data.portfolios.map((p) => ({ vol: p.vol_pct, ret: p.exp_return_pct, name: SHORT[p.name] ?? p.name }));
  return (
    <div className="flex flex-col gap-4">
      <InsightBox insight={data.insight} />

      <SectionTitle>Weights by method</SectionTitle>
      <ChartTitle>How each method splits 100% across the basket</ChartTitle>
      <div className="h-60 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={weightRows} layout="vertical" margin={{ top: 4, right: 8, bottom: 0, left: 4 }} stackOffset="expand">
            <XAxis type="number" tick={AXIS_TICK} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
            <YAxis type="category" dataKey="name" tick={{ ...AXIS_TICK, fontSize: 10 }} width={72} />
            <Tooltip contentStyle={TIP_STYLE} formatter={(v, n) => [`${Number(v).toFixed(1)}%`, String(n)]} />
            <Legend wrapperStyle={{ fontSize: 10 }} />
            {data.assets.map((a, i) => (
              <Bar key={a} dataKey={a} stackId="w" fill={PALETTE[i % PALETTE.length]} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="warm-scroll overflow-x-auto">
        <table className="w-full min-w-[600px] text-right text-[11px]">
          <thead className="text-[9px] uppercase text-[#b39a76]">
            <tr>
              <th className="text-left">Method</th><th>Exp. return</th><th>Vol</th><th>Sharpe</th><th>Max DD</th><th>Div. ratio</th>
              <th>{symbol} weight</th><th>{symbol} risk share</th>
            </tr>
          </thead>
          <tbody className="font-mono text-[#5c4327]">
            <tr className="border-t border-[#f4ead2] bg-[#fdf8ec]">
              <td className="py-1 text-left font-sans italic">{symbol} alone</td>
              <td style={{ color: signColor(data.alone.exp_return_pct) }}>{fmtSigned(data.alone.exp_return_pct, 1)}</td>
              <td>{data.alone.vol_pct.toFixed(1)}%</td><td>{data.alone.sharpe.toFixed(2)}</td>
              <td className="text-[#c9553f]">{data.alone.max_dd_pct.toFixed(0)}%</td><td>1.00</td><td>100%</td><td>100%</td>
            </tr>
            {data.portfolios.map((p) => (
              <tr key={p.name} className="border-t border-[#f4ead2]">
                <td className="py-1 text-left font-sans">{p.name}</td>
                <td style={{ color: signColor(p.exp_return_pct) }}>{fmtSigned(p.exp_return_pct, 1)}</td>
                <td>{p.vol_pct.toFixed(1)}%</td><td className="font-semibold">{p.sharpe.toFixed(2)}</td>
                <td className="text-[#c9553f]">{p.max_dd_pct.toFixed(0)}%</td><td>{p.diversification_ratio.toFixed(2)}</td>
                <td>{p.weights[0].toFixed(0)}%</td><td>{p.risk_contrib[0].toFixed(0)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[10px] text-[#b39a76]">
        Diversification ratio &gt; 1 = the basket is calmer than its parts. Risk share = % of portfolio volatility coming from {symbol}.
        Window {data.window.start} → {data.window.end}. {data.method}
      </p>

      <SectionTitle>Efficient frontier</SectionTitle>
      <ChartTitle>Risk (x, vol %) vs expected return (y, %/yr): 600 random baskets (beige), the frontier (copper), assets (teal), the six methods (rose diamonds — hover for names)</ChartTitle>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 6, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="#f4ead2" />
            <XAxis type="number" dataKey="vol" name="Vol" unit="%" tick={AXIS_TICK} domain={['auto', 'auto']} />
            <YAxis type="number" dataKey="ret" name="Return" unit="%" tick={AXIS_TICK} width={36} domain={['auto', 'auto']} />
            <ZAxis range={[14, 14]} />
            <Tooltip contentStyle={TIP_STYLE} cursor={{ strokeDasharray: '3 3' }}
              formatter={(v, n) => [`${Number(v).toFixed(2)}%`, String(n)]}
              labelFormatter={() => ''} />
            <Scatter name="Random" data={data.cloud} fill="rgba(201,170,120,0.35)" isAnimationActive={false} />
            <Scatter name="Frontier" data={data.frontier} fill={C.copper} line={{ stroke: C.copper, strokeWidth: 2 }} shape={() => <g />} isAnimationActive={false} />
            <Scatter name="Assets" data={data.asset_points} fill={C.teal} isAnimationActive={false}
              shape={(p: { cx?: number; cy?: number; payload?: { symbol: string } }) => (
                <g>
                  <circle cx={p.cx} cy={p.cy} r={4} fill={C.teal} />
                  <text x={(p.cx ?? 0) + 6} y={(p.cy ?? 0) + 3} fontSize={9} fill="#2f6f69">{p.payload?.symbol}</text>
                </g>
              )} />
            <Scatter name="Methods" data={portPts} fill={C.rose} isAnimationActive={false}
              shape={(p: { cx?: number; cy?: number; payload?: { name: string } }) => (
                <g>
                  <rect x={(p.cx ?? 0) - 3.5} y={(p.cy ?? 0) - 3.5} width={7} height={7} fill={C.rose} transform={`rotate(45 ${p.cx} ${p.cy})`} />
                  {(p.payload?.name === 'Max-Sharpe' || p.payload?.name === 'Min-var') && (
                    <text x={(p.cx ?? 0) + 6} y={(p.cy ?? 0) + (p.payload?.name === 'Min-var' ? 12 : -4)} fontSize={9} fill="#9b3f55">{p.payload?.name}</text>
                  )}
                </g>
              )} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <p className="text-[10px] text-[#b39a76]">Points on the copper curve give the most return for each level of risk; anything below it is a less efficient mix.</p>

      <SectionTitle>Basket correlation (shrunk covariance)</SectionTitle>
      <HeatGrid
        rows={data.assets}
        cols={data.assets}
        values={data.corr}
        style={(v) => divergeStyle(v, 0.9)}
        fmt={(v) => (v === null ? '·' : v.toFixed(2).replace('0.', '.'))}
        minWidth={420}
      />
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {data.asset_stats.map((a) => (
          <div key={a.symbol} className="min-w-0 rounded-lg border border-[#f0e4cc] bg-[#fffdf6] px-2 py-1.5">
            <p className="truncate text-[10px] font-semibold text-[#5c4327]" title={a.name}>{a.symbol} · {a.name}</p>
            <p className="font-mono text-[11px]" style={{ color: signColor(a.ret_pct) }}>
              {fmtSigned(a.ret_pct, 1)}/yr <span className="text-[#97795a]">· vol {a.vol_pct.toFixed(0)}% · SR {a.sharpe.toFixed(2)}</span>
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
