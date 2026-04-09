import { getApiBaseUrl } from "@/lib/config";

const API_BASE = getApiBaseUrl();

export interface Tag {
  id: number;
  name: string;
  created_at: string;
}

export interface ContentItem {
  id: number;
  type: "briefing" | "setup" | "macro_roundup" | "contrarian_alert";
  content_type?: "briefing" | "setup" | "macro_roundup" | "contrarian_alert"; // backend alias
  title: string;
  instrument?: string;       // frontend uses this
  instrument_symbol?: string; // backend sends this
  direction?: "long" | "short" | "neutral";
  entry_zone?: string;
  stop_loss?: string;
  take_profit?: string;
  timeframe?: "scalp" | "h4" | "d1" | "w1";
  confidence?: "high" | "medium" | "low";
  rationale: string;
  tags: string[];
  published_at: string;
  featured: boolean;
}

// Normalize raw API response to frontend format
function normalizeContentItem(raw: Record<string, unknown>): ContentItem {
  // Tags: backend sends [{id, name, created_at}], frontend wants string[]
  let tags: string[] = [];
  if (Array.isArray(raw.tags)) {
    tags = raw.tags.map((t: Record<string, unknown>) =>
      typeof t === "string" ? t : (t.name as string)
    );
  }

  return {
    id: raw.id as number,
    type: (raw.type as string) as ContentItem["type"]
      || (raw.content_type as string) as ContentItem["type"],
    title: raw.title as string,
    instrument: (raw.instrument as string)
      || (raw.instrument_symbol as string)
      || "",
    direction: raw.direction as ContentItem["direction"],
    entry_zone: raw.entry_zone as string | undefined,
    stop_loss: raw.stop_loss as string | undefined,
    take_profit: raw.take_profit as string | undefined,
    timeframe: raw.timeframe as ContentItem["timeframe"],
    confidence: raw.confidence as ContentItem["confidence"],
    rationale: raw.rationale as string,
    tags,
    published_at: raw.published_at as string,
    featured: Boolean(raw.featured),
  };
}

function normalizeContentItems(raws: unknown[]): ContentItem[] {
  return (raws as Record<string, unknown>[]).map(normalizeContentItem);
}

export interface Instrument {
  symbol: string;
  name: string;
  asset_class: "FX" | "Commodities" | "Crypto" | "Indices" | "fx" | "commodities" | "crypto" | "indices";
}

export interface ContentFilters {
  type?: string;
  content_type?: string;
  asset_class?: string;
  direction?: string;
  timeframe?: string;
  confidence?: string;
  tag?: string;
  search?: string;
  featured?: boolean;
}

async function fetchAPI<T>(endpoint: string): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    cache: "no-store",
    redirect: "follow",
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}

// ─── Content ─────────────────────────────────────────────────────────────────

export async function getContent(filters: ContentFilters = {}): Promise<ContentItem[]> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      // Map frontend filter names to backend names
      const backendKey = key === "type" ? "content_type" : key;
      params.append(backendKey, String(value));
    }
  });
  const query = params.toString();
  const raw = await fetchAPI<Record<string, unknown>[]>(`/content${query ? `?${query}` : ""}`);
  return normalizeContentItems(raw);
}

export async function getContentById(id: string): Promise<ContentItem> {
  const raw = await fetchAPI<Record<string, unknown>>(`/content/${id}`);
  return normalizeContentItem(raw);
}

export async function getFeaturedContent(): Promise<ContentItem[]> {
  const raw = await fetchAPI<Record<string, unknown>[]>(`/content/?featured=true&limit=6`);
  return normalizeContentItems(raw);
}

// Trigger the full daily content generation pipeline (briefings + setups + roundup + contrarian)
export async function runFullPipeline(): Promise<{ total_count: number; message: string }> {
  const adminKey = process.env.NEXT_PUBLIC_ADMIN_API_KEY;
  const headers: Record<string, string> = {};
  if (adminKey) headers["X-Admin-Key"] = adminKey;
  const res = await fetch(`${API_BASE}/admin/generate/full`, { method: "POST", headers });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Pipeline failed: ${res.status} ${body}`);
  }
  const data = await res.json();
  return { total_count: data.total_count ?? 0, message: data.message ?? "Pipeline completed" };
}

// ─── Instruments ─────────────────────────────────────────────────────────────

export async function getInstruments(): Promise<Instrument[]> {
  return fetchAPI<Instrument[]>("/instruments");
}

export async function getInstrument(symbol: string): Promise<Instrument> {
  return fetchAPI<Instrument>(`/instruments/symbol/${encodeURIComponent(symbol)}`);
}

export async function getContentByInstrument(symbol: string): Promise<ContentItem[]> {
  const raw = await fetchAPI<Record<string, unknown>[]>(`/instruments/symbol/${encodeURIComponent(symbol)}/content`);
  return normalizeContentItems(raw);
}


// ─── News ──────────────────────────────────────────────────────────────────

export interface NewsItem {
  id: number;
  title: string;
  description?: string;
  url: string;
  published_at?: string;
  is_read: boolean;
  is_starred: boolean;
  tags?: string;
  source_name: string;
  source_category: string;
}

export interface NewsSource {
  id: number;
  category: string;
  name: string;
  url: string;
  enabled: boolean;
  last_fetched_at?: string;
  last_error?: string;
  fetch_count: number;
  created_at: string;
}

export interface NewsListResponse {
  items: NewsItem[];
  total: number;
  limit: number;
  offset: number;
}

export async function getNews(filters: {
  category?: string;
  source?: string;
  is_read?: boolean;
  is_starred?: boolean;
  limit?: number;
  offset?: number;
} = {}): Promise<NewsListResponse> {
  const params = new URLSearchParams();
  if (filters.category) params.append("category", filters.category);
  if (filters.source) params.append("source", filters.source);
  if (filters.is_read !== undefined) params.append("is_read", String(filters.is_read));
  if (filters.is_starred !== undefined) params.append("is_starred", String(filters.is_starred));
  if (filters.limit) params.append("limit", String(filters.limit));
  if (filters.offset) params.append("offset", String(filters.offset));
  const query = params.toString();
  return fetchAPI<NewsListResponse>(`/news/${query ? `?${query}` : ""}`);
}

export async function getNewsCategories(): Promise<string[]> {
  return fetchAPI<string[]>("/news/categories");
}

export async function getNewsSources(filters: { category?: string; enabled?: boolean } = {}): Promise<NewsSource[]> {
  const params = new URLSearchParams();
  if (filters.category) params.append("category", filters.category);
  if (filters.enabled !== undefined) params.append("enabled", String(filters.enabled));
  const query = params.toString();
  return fetchAPI<NewsSource[]>(`/news/sources${query ? `?${query}` : ""}`);
}

export async function fetchNews(category?: string): Promise<{ sources_updated: number; new_items: number; errors: number }> {
  const body = category ? { category } : {};
  const res = await fetch(`${API_BASE}/news/fetch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function markNewsRead(itemId: number, isRead: boolean): Promise<void> {
  const res = await fetch(`${API_BASE}/news/${itemId}/read?is_read=${isRead}`, {
    method: "PATCH",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

export async function markNewsStarred(itemId: number, isStarred: boolean): Promise<void> {
  const res = await fetch(`${API_BASE}/news/${itemId}/star?is_starred=${isStarred}`, {
    method: "PATCH",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}


// ─── Trading Signals ──────────────────────────────────────────────────────────

export interface SignalStage1 {
  market_regime: string;
  volatility_regime: string;
  trading_mode: string;
  position_size_modifier: number;
  regime_reasoning?: string;
  vix_signal?: string;
}

export interface SignalStage2 {
  fundamental_bias: string;
  bias_strength: string;
  top_drivers: string[];
  fundamental_reasoning?: string;
  swing_trade_aligned?: boolean;
}

export interface SignalStage3 {
  gate_signal: string;
  entry_recommendation: string;
  technical_alignment: string;
  gate_reasoning?: string;
  watch_list_trigger?: string;
}

export interface SignalStage4 {
  final_signal: string;
  signal_confidence: number;
  direction: string;
  entry_price: number;
  stop_loss: number;
  target_price: number;
  risk_reward_ratio: number;
  recommended_position_size_pct: number;
  trade_horizon: string;
  signal_summary: string;
  key_risks: string[];
  invalidation_conditions: string[];
}

export interface FSMContext {
  available?: boolean;
  fed_regime?: string;
  composite_score?: number;
  language_score?: number;
  market_score?: number;
  is_pivot_in_progress?: boolean;
  volatility_multiplier?: number;
  divergence_category?: string;
  signal_direction?: string;
  signal_conviction?: string;
  position_size_modifier?: number;
  days_to_next_fomc?: number | null;
  next_fomc_date?: string | null;
  pre_fomc_window?: boolean;
}

export interface TradingSignal {
  id?: number;
  asset: string;
  asset_class: string;
  generated_at?: string;
  outcome?: string;
  // Stage 1
  market_regime?: string;
  volatility_regime?: string;
  trading_mode?: string;
  position_size_modifier?: number;
  // Stage 2
  fundamental_bias?: string;
  bias_strength?: string;
  top_drivers?: string[];
  // Stage 3
  gate_signal?: string;
  entry_recommendation?: string;
  technical_alignment?: string;
  // Trade params
  entry_price?: number;
  stop_loss?: number;
  target_price?: number;
  risk_reward_ratio?: number;
  // Stage 4
  final_signal?: string;
  signal_grade?: string;
  signal_confidence?: number;
  direction?: string;
  recommended_position_size_pct?: number;
  trade_horizon?: string;
  trade_type?: string;
  signal_summary?: string;
  key_risks?: string[];
  invalidation_conditions?: string[];
  target_2_price?: number;
  target_3_price?: number;
  macro_quadrant?: string;
  // FSM context snapshot at generation time
  fsm_context?: FSMContext | null;
  // Full stage outputs (when include_stages=true)
  stage1?: SignalStage1;
  stage2?: SignalStage2;
  stage3?: SignalStage3;
  stage4?: SignalStage4;
}

export interface SignalListResponse {
  items: TradingSignal[];
  total: number;
  limit: number;
  offset: number;
}

export interface SignalStats {
  total_signals: number;
  active: number;
  resolved: number;
  win_rate: number | null;
  avg_confidence: number | null;
  by_regime: Record<string, number>;
  by_direction: Record<string, number>;
}

export async function getSignals(filters: {
  asset?: string;
  outcome?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<SignalListResponse> {
  const params = new URLSearchParams();
  if (filters.asset) params.append("asset", filters.asset);
  if (filters.outcome) params.append("outcome", filters.outcome);
  if (filters.limit) params.append("limit", String(filters.limit));
  if (filters.offset) params.append("offset", String(filters.offset));
  const query = params.toString();
  return fetchAPI<SignalListResponse>(`/signals/${query ? `?${query}` : ""}`);
}

export async function getSignalStats(): Promise<SignalStats> {
  return fetchAPI<SignalStats>("/signals/stats/summary");
}

export async function generateSignal(asset: string): Promise<TradingSignal> {
  const res = await fetch(`${API_BASE}/signals/generate?asset=${encodeURIComponent(asset)}`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function resolveSignal(signalId: number, outcome: "WIN" | "LOSS" | "BREAKEVEN", notes?: string): Promise<void> {
  const params = new URLSearchParams({ signal_id: String(signalId), outcome });
  if (notes) params.append("notes", notes);
  const res = await fetch(`${API_BASE}/signals/resolve?${params}`, {
    method: "PATCH",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}


// ─── Trade Outcomes ───────────────────────────────────────────────────────────

export interface TradeOutcome {
  id: number;
  content_item_id: number;
  status: "open" | "won" | "lost" | "breakeven" | "cancelled";
  result_note?: string;
  actual_entry?: string;
  actual_sl?: string;
  actual_tp?: string;
  pnl_pips?: number;
  outcome_date?: string;
  created_at: string;
  updated_at: string;
  content_title?: string;
  instrument_symbol?: string;
}

export interface OutcomeListResponse {
  items: TradeOutcome[];
  total: number;
  limit: number;
  offset: number;
}

export interface OutcomeStats {
  total_setups: number;
  open_count: number;
  won_count: number;
  lost_count: number;
  breakeven_count: number;
  cancelled_count: number;
  resolved_count: number;
  win_rate: number | null;
  avg_pnl_pips: number | null;
  avg_risk_reward: number | null;
  by_instrument: Record<string, { total: number; won: number; lost: number; breakeven?: number; win_rate: number | null }>;
  by_direction: Record<string, { total: number; won: number; lost: number; win_rate: number | null }>;
  by_timeframe: Record<string, { total: number; won: number; lost: number; win_rate: number | null }>;
  by_confidence: Record<string, { total: number; won: number; lost: number; win_rate: number | null }>;
  by_tag: Record<string, { total: number; won: number; lost: number; win_rate: number | null }>;
}

export async function getTradeOutcomes(filters: {
  status?: string;
  instrument?: string;
  timeframe?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<OutcomeListResponse> {
  const params = new URLSearchParams();
  if (filters.status) params.append("status", filters.status);
  if (filters.instrument) params.append("instrument", filters.instrument);
  if (filters.timeframe) params.append("timeframe", filters.timeframe);
  if (filters.limit) params.append("limit", String(filters.limit));
  if (filters.offset) params.append("offset", String(filters.offset));
  const query = params.toString();
  return fetchAPI<OutcomeListResponse>(`/trade-outcomes/${query ? `?${query}` : ""}`);
}

export async function getOutcomeStats(): Promise<OutcomeStats> {
  return fetchAPI<OutcomeStats>("/trade-outcomes/stats");
}

export async function createOrUpdateOutcome(data: {
  content_item_id: number;
  status?: string;
  result_note?: string;
  actual_entry?: string;
  actual_sl?: string;
  actual_tp?: string;
  pnl_pips?: number;
  outcome_date?: string;
}): Promise<TradeOutcome> {
  const res = await fetch(`${API_BASE}/trade-outcomes/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}


// ─── COT History ──────────────────────────────────────────────────────────────

export interface COTSnapshot {
  id: number;
  report_date: string;
  instrument: string;
  commercial_long: number;
  commercial_short: number;
  commercial_net: number;
  noncommercial_long: number;
  noncommercial_short: number;
  noncommercial_net: number;
  open_interest: number;
  created_at: string;
}

export interface COTListResponse {
  items: COTSnapshot[];
  total: number;
  limit: number;
  offset: number;
}

export interface COTLatestItem {
  instrument: string;
  report_date: string | null;
  commercial_long: number;
  commercial_short: number;
  commercial_net: number;
  noncommercial_long: number;
  noncommercial_short: number;
  noncommercial_net: number;
  open_interest: number;
}

export interface COTLatestResponse {
  instruments: COTLatestItem[];
}

export async function getCOTHistory(filters: {
  instrument?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<COTListResponse> {
  const params = new URLSearchParams();
  if (filters.instrument) params.append("instrument", filters.instrument);
  if (filters.date_from) params.append("date_from", filters.date_from);
  if (filters.date_to) params.append("date_to", filters.date_to);
  if (filters.limit) params.append("limit", String(filters.limit));
  if (filters.offset) params.append("offset", String(filters.offset));
  const query = params.toString();
  return fetchAPI<COTListResponse>(`/cot-history/${query ? `?${query}` : ""}`);
}

export async function getCOTLatest(): Promise<COTLatestResponse> {
  return fetchAPI<COTLatestResponse>("/cot-history/latest");
}

export async function scrapeCOTData(): Promise<{ success: boolean; instruments_updated: string[]; errors: string[] }> {
  const res = await fetch(`${API_BASE}/cot-history/scrape`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}


// ─── Market Regime ─────────────────────────────────────────────────────────────

export interface RegimeItem {
  instrument: string;
  trend: "TRENDING_UP" | "TRENDING_DOWN" | "RANGING";
  rsi: number;
  atr_percent: number;
  volatility_regime: "LOW" | "NORMAL" | "HIGH";
  confidence: "HIGH" | "MEDIUM" | "LOW";
  signals: string[];
  regime_history: Array<{
    regime: string;
    rsi_14: number;
    atr_percent: number;
    trend: string;
    recorded_at: string | null;
  }>;
}

export interface RegimeResponse {
  items: RegimeItem[];
  generated_at: string;
}

export async function getRegime(): Promise<RegimeResponse> {
  return fetchAPI<RegimeResponse>("/regime/");
}

export async function getRegimeByInstrument(instrument: string): Promise<RegimeItem> {
  return fetchAPI<RegimeItem>(`/regime/${instrument.toUpperCase()}`);
}


// ─── Multi-Timeframe Analysis ──────────────────────────────────────────────────

export interface TimeframeData {
  timeframe: "H4" | "D1" | "W1";
  current_price: number;
  trend: "TRENDING_UP" | "TRENDING_DOWN" | "RANGING";
  rsi_14: number;
  ma_20: number;
  ma_60: number;
  key_support: number;
  key_resistance: number;
  atr_14: number;
  signals: string[];
}

export interface SetupItem {
  id: number;
  title: string;
  direction?: string;
  timeframe?: string;
  confidence?: string;
  entry_zone?: string;
  stop_loss?: string;
  take_profit?: string;
  risk_reward_ratio?: number;
  published_at?: string;
}

export interface MultiTimeframeResponse {
  instrument: string;
  timeframes: TimeframeData[];
  consensus: "BULLISH" | "BEARISH" | "MIXED";
  setups: SetupItem[];
}

export async function getMultiTimeframe(instrument: string): Promise<MultiTimeframeResponse> {
  return fetchAPI<MultiTimeframeResponse>(`/multi-timeframe/${encodeURIComponent(instrument.toUpperCase())}`);
}

export async function generateSetup(instrument: string): Promise<{ items: SetupItem[]; message: string }> {
  const res = await fetch(`${API_BASE}/admin/generate/setup?instrument=${encodeURIComponent(instrument.toUpperCase())}`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}


// ─── Alert Rules ───────────────────────────────────────────────────────────────

export interface AlertRule {
  id: number;
  name: string;
  instrument: string | null;
  condition_type: string;
  condition_params: Record<string, unknown>;
  enabled: boolean;
  notify_via: string;
  last_triggered: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertLog {
  id: number;
  alert_rule_id: number;
  triggered_at: string;
  message: string;
  acknowledged: boolean;
  alert_rule?: AlertRule;
}

export interface CreateAlertRuleData {
  name: string;
  instrument?: string | null;
  condition_type: string;
  condition_params?: Record<string, unknown>;
  enabled?: boolean;
  notify_via?: string;
}

export async function getAlertRules(filters?: {
  instrument?: string;
  enabled?: boolean;
}): Promise<AlertRule[]> {
  const params = new URLSearchParams();
  if (filters?.instrument) params.append("instrument", filters.instrument);
  if (filters?.enabled !== undefined) params.append("enabled", String(filters.enabled));
  const query = params.toString();
  return fetchAPI<AlertRule[]>(`/alerts/alert-rules${query ? `?${query}` : ""}`);
}

export async function createAlertRule(data: CreateAlertRuleData): Promise<AlertRule> {
  const res = await fetch(`${API_BASE}/alerts/alert-rules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function deleteAlertRule(ruleId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/alerts/alert-rules/${ruleId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

export async function testAlertRule(ruleId: number): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/alerts/alert-rules/${ruleId}/test`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function updateAlertRule(
  ruleId: number,
  data: Partial<CreateAlertRuleData>
): Promise<AlertRule> {
  const res = await fetch(`${API_BASE}/alerts/alert-rules/${ruleId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getAlertLogs(filters?: {
  rule_id?: number;
  acknowledged?: boolean;
  limit?: number;
}): Promise<AlertLog[]> {
  const params = new URLSearchParams();
  if (filters?.rule_id) params.append("rule_id", String(filters.rule_id));
  if (filters?.acknowledged !== undefined) params.append("acknowledged", String(filters.acknowledged));
  if (filters?.limit) params.append("limit", String(filters.limit));
  const query = params.toString();
  return fetchAPI<AlertLog[]>(`/alerts/alert-logs${query ? `?${query}` : ""}`);
}

export async function acknowledgeAlertLog(logId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/alerts/alert-logs/${logId}/acknowledge`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}


// ─── Correlation Matrix ────────────────────────────────────────────────────────

export interface CorrelationResponse {
  instruments: string[];
  matrix: number[][];
  timeframe: string;
  computed_at: string;
  strongest_positive: [string, string, number];
  strongest_negative: [string, string, number];
}

export async function getCorrelation(filters?: {
  instruments?: string;
  timeframe?: string;
}): Promise<CorrelationResponse> {
  const params = new URLSearchParams();
  if (filters?.instruments) params.append("instruments", filters.instruments);
  if (filters?.timeframe) params.append("timeframe", filters.timeframe);
  const query = params.toString();
  return fetchAPI<CorrelationResponse>(`/correlation/${query ? `?${query}` : ""}`);
}


// ─── Economic Calendar ─────────────────────────────────────────────────────────

export interface EconEvent {
  id: number;
  event_date: string;
  country: string;
  event_name: string;
  importance: "low" | "medium" | "high";
  currency: string;
  previous: string | null;
  forecast: string | null;
  actual: string | null;
  impact: "low" | "medium" | "high";
  source: string;
  scraped_at: string | null;
  created_at: string;
  updated_at: string;
  impacted_instruments?: string[];
}

export interface EconEventListResponse {
  items: EconEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface UpcomingEventsResponse {
  items: EconEvent[];
  total: number;
  days: number;
}

export interface EconScrapeResponse {
  success: boolean;
  events_created: number;
  events_updated: number;
  errors: string[];
}

export interface ImpactMapResponse {
  mappings: Record<string, string[]>;
  countries: Record<string, { currency: string; flag: string }>;
}

export async function getEconEvents(filters?: {
  start_date?: string;
  end_date?: string;
  country?: string;
  importance?: string;
  currency?: string;
  limit?: number;
  offset?: number;
}): Promise<EconEventListResponse> {
  const params = new URLSearchParams();
  if (filters?.start_date) params.append("start_date", filters.start_date);
  if (filters?.end_date) params.append("end_date", filters.end_date);
  if (filters?.country) params.append("country", filters.country);
  if (filters?.importance) params.append("importance", filters.importance);
  if (filters?.currency) params.append("currency", filters.currency);
  if (filters?.limit) params.append("limit", String(filters.limit));
  if (filters?.offset) params.append("offset", String(filters.offset));
  const query = params.toString();
  return fetchAPI<EconEventListResponse>(`/economic-calendar/${query ? `?${query}` : ""}`);
}

export async function getUpcomingEconEvents(filters?: {
  days?: number;
  country?: string;
  importance?: string;
}): Promise<UpcomingEventsResponse> {
  const params = new URLSearchParams();
  if (filters?.days) params.append("days", String(filters.days));
  if (filters?.country) params.append("country", filters.country);
  if (filters?.importance) params.append("importance", filters.importance);
  const query = params.toString();
  return fetchAPI<UpcomingEventsResponse>(`/economic-calendar/upcoming${query ? `?${query}` : ""}`);
}

export async function createEconEvent(data: {
  event_date: string;
  country: string;
  event_name: string;
  importance?: string;
  currency: string;
  previous?: string;
  forecast?: string;
  actual?: string;
  impact?: string;
}): Promise<EconEvent> {
  const res = await fetch(`${API_BASE}/economic-calendar/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function updateEconEvent(
  eventId: number,
  data: Partial<{
    event_date: string;
    country: string;
    event_name: string;
    importance: string;
    currency: string;
    previous: string;
    forecast: string;
    actual: string;
    impact: string;
  }>
): Promise<EconEvent> {
  const res = await fetch(`${API_BASE}/economic-calendar/${eventId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function deleteEconEvent(eventId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/economic-calendar/${eventId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

export async function scrapeEconEvents(): Promise<EconScrapeResponse> {
  const res = await fetch(`${API_BASE}/economic-calendar/scrape`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getImpactMap(): Promise<ImpactMapResponse> {
  return fetchAPI<ImpactMapResponse>("/economic-calendar/impact-map");
}

// ─── News Analysis (AI) ─────────────────────────────────────────────────────

export interface InstrumentImpact {
  instrument: string;
  direction: "Bullish" | "Bearish" | "Neutral";
}

export interface NewsAnalysis {
  summary: string;
  instruments: InstrumentImpact[];
  regime_note: string;
}

export interface NewsAskResponse {
  answer: string;
}

export async function analyzeNews(article: {
  title: string;
  description: string;
  source: string;
  sentiment_score?: number;
  sentiment_label?: string;
}): Promise<NewsAnalysis> {
  const res = await fetch(`${API_BASE}/news/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: article.title,
      description: article.description,
      source: article.source,
      sentiment_score: article.sentiment_score ?? null,
      sentiment_label: article.sentiment_label ?? null,
    }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function askAboutNews(params: {
  title: string;
  description: string;
  question: string;
  analysis_summary?: string;
  conversation?: { role: string; text: string }[];
}): Promise<NewsAskResponse> {
  const res = await fetch(`${API_BASE}/news/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: params.title,
      description: params.description,
      question: params.question,
      analysis_summary: params.analysis_summary ?? "",
      conversation: params.conversation ?? [],
    }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}


// ─── Fed Sentiment Module ──────────────────────────────────────────────────────

export interface FedComposite {
  composite_score: number | null;
  language_score: number | null;
  market_score: number | null;
  divergence_score: number | null;
  divergence_category: string | null;
  divergence_zscore: number | null;
  fed_regime: string | null;
  trading_signal: string | null;
  signal_conviction: string | null;
  signal_direction: string | null;
  yield_2y: number | null;
  yield_spread_10y2y: number | null;
  fed_target_rate: number | null;
  yield_2y_30d_change: number | null;
  key_phrases: string[];
  is_stale: boolean;
  generated_at: string;
  days_to_next_fomc: number | null;
  next_fomc_date: string | null;
}

export interface FedMarketExpectations {
  market_score: number | null;
  yield_2y: number | null;
  yield_spread_10y2y: number | null;
  fed_target_rate: number | null;
  yield_2y_30d_change: number | null;
  next_meeting_bps_priced: number | null;
  is_stale: boolean;
  fetched_at: string;
}

export interface FedDocument {
  id: number;
  document_type: string;
  document_date: string;
  speaker: string | null;
  title: string;
  source_url: string | null;
  tier1_score: number | null;
  blended_score: number | null;
  importance_weight: number;
  created_at: string;
}

export interface FedHistoryItem {
  timestamp: string;
  composite_score: number | null;
  language_score: number | null;
  market_score: number | null;
  divergence_score: number | null;
  fed_regime: string | null;
  signal_direction: string | null;
}

export async function getFedComposite(): Promise<FedComposite> {
  return fetchAPI<FedComposite>("/fed-sentiment/composite");
}

export async function getFedMarketExpectations(): Promise<FedMarketExpectations> {
  return fetchAPI<FedMarketExpectations>("/fed-sentiment/market");
}

export async function getFedDocuments(days?: number): Promise<FedDocument[]> {
  const q = days ? `?days=${days}` : "";
  return fetchAPI<FedDocument[]>(`/fed-sentiment/documents${q}`);
}

export async function getFedHistory(days?: number): Promise<FedHistoryItem[]> {
  const q = days ? `?days=${days}` : "";
  return fetchAPI<FedHistoryItem[]>(`/fed-sentiment/history${q}`);
}

export async function syncFedDocuments(): Promise<{ synced_count: number; message: string }> {
  const res = await fetch(`${API_BASE}/fed-sentiment/sync`, { method: "POST" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function scoreFedTier2(maxDocs?: number): Promise<{ scored_count: number; message: string }> {
  const q = maxDocs ? `?max_docs=${maxDocs}` : "";
  const res = await fetch(`${API_BASE}/fed-sentiment/score-tier2${q}`, { method: "POST" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface PhraseTransitionItem {
  id: number;
  phrase_from: string;
  phrase_to: string;
  signal_type: string | null;
  description: string | null;
  doc_from_date: string | null;
  doc_to_date: string | null;
  detected_at: string | null;
}

export async function getFedPhraseTransitions(limit?: number): Promise<PhraseTransitionItem[]> {
  const q = limit ? `?limit=${limit}` : "";
  return fetchAPI<PhraseTransitionItem[]>(`/fed-sentiment/phrase-transitions${q}`);
}

export async function detectPhraseTransitions(): Promise<{ detected: number; message: string }> {
  const res = await fetch(`${API_BASE}/fed-sentiment/detect-transitions`, { method: "POST" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ─── V3 Backtest ───────────────────────────────────────────────────────────────

export interface V3BacktestRunSummary {
  run_id: string;
  total_signals: number;
  actionable: number;
  closed: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  total_pnl_pct: number;
  started_at: string | null;
  last_signal_at: string | null;
}

export interface V3BacktestPerAsset {
  total_signals: number;
  actionable: number;
  wins: number;
  losses: number;
  open: number;
  not_triggered: number;
  no_trade: number;
  errors: number;
  closed: number;
  win_rate: number | null;
  avg_r: number | null;
  total_pnl_pct: number;
}

export interface V3BacktestRunDetail {
  run_id: string;
  total_signals: number;
  total_closed: number;
  total_wins: number;
  portfolio_win_rate: number | null;
  portfolio_pnl_pct: number;
  per_asset: Record<string, V3BacktestPerAsset>;
}

export interface V3BacktestSignal {
  id: number;
  asset: string;
  as_of_date: string;
  final_signal: string | null;
  direction: string | null;
  signal_confidence: number | null;
  market_regime: string | null;
  fundamental_bias: string | null;
  gate_signal: string | null;
  entry_price: number | null;
  stop_loss: number | null;
  target_price: number | null;
  risk_reward_ratio: number | null;
  fsm_composite_score: number | null;
  fsm_divergence_category: string | null;
  outcome: string | null;
  entry_triggered: boolean;
  entry_actual_price: number | null;
  exit_price: number | null;
  pnl_pct: number | null;
  r_multiple: number | null;
  bars_in_trade: number | null;
  max_favorable_excursion_pct: number | null;
  max_adverse_excursion_pct: number | null;
}

export interface V3EquityCurve {
  run_id: string;
  asset: string | null;
  points: Array<{
    date: string;
    asset: string;
    pnl_pct: number;
    cumulative_pct: number;
    drawdown_pct: number;
    outcome: string;
  }>;
  max_drawdown_pct: number;
  final_pnl_pct: number;
  trades_count: number;
}

export async function getV3BacktestRuns(): Promise<V3BacktestRunSummary[]> {
  return fetchAPI<V3BacktestRunSummary[]>("/v3-backtest/runs");
}

export async function getV3BacktestRunDetail(runId: string): Promise<V3BacktestRunDetail> {
  return fetchAPI<V3BacktestRunDetail>(`/v3-backtest/runs/${encodeURIComponent(runId)}`);
}

export async function getV3BacktestSignals(
  runId: string,
  filters?: { asset?: string; outcome?: string; limit?: number }
): Promise<V3BacktestSignal[]> {
  const params = new URLSearchParams();
  if (filters?.asset) params.set("asset", filters.asset);
  if (filters?.outcome) params.set("outcome", filters.outcome);
  if (filters?.limit) params.set("limit", String(filters.limit));
  const qs = params.toString();
  return fetchAPI<V3BacktestSignal[]>(
    `/v3-backtest/runs/${encodeURIComponent(runId)}/signals${qs ? "?" + qs : ""}`
  );
}

export async function getV3EquityCurve(runId: string, asset?: string): Promise<V3EquityCurve> {
  const params = asset ? `?asset=${encodeURIComponent(asset)}` : "";
  return fetchAPI<V3EquityCurve>(`/v3-backtest/runs/${encodeURIComponent(runId)}/equity-curve${params}`);
}

// ─── FSM Backtest ──────────────────────────────────────────────────────────────

export interface BacktestEvent {
  date: string;
  event: string;
  expected_signal: string;
  expected_direction: string;
  expected_dxy_move: string;
  narrative: string;
  status: string;
  tier1_score?: number;
  tier2_score?: number | null;
  final_score?: number;
  predicted_direction?: string;
  actual_direction?: string | null;
  direction_correct?: boolean | null;
  dxy_reaction?: {
    available?: boolean;
    source?: string;
    intraday_pct?: number;
    next_day_pct?: number;
    composite_24h_pct?: number;
    pct_1m?: number;
    pct_10m?: number;
    pct_30m?: number;
    pct_90m?: number;
    pct_120m?: number;
  };
  key_phrases_sample?: string[];
  press_conference_available?: boolean;
  press_conference_t1?: number | null;
  press_conference_t2?: number | null;
}

export interface BacktestResult {
  ran_at: string | null;
  use_tier2: boolean;
  total_events?: number;
  events_processed?: number;
  metrics: {
    direction_accuracy?: number | null;
    direction_correct?: number;
    direction_evaluated?: number;
    surprise_detection_rate?: number | null;
    surprise_detected?: number;
    surprise_total?: number;
    priced_in_accuracy?: number | null;
    priced_in_correct?: number;
    priced_in_total?: number;
  };
  events: BacktestEvent[];
  message?: string;
}

export async function getFedBacktest(useTier2 = false): Promise<BacktestResult> {
  return fetchAPI<BacktestResult>(`/fed-sentiment/backtest?use_tier2=${useTier2}`);
}

export async function runFedBacktest(useTier2 = false): Promise<BacktestResult> {
  const res = await fetch(`${API_BASE}/fed-sentiment/backtest?use_tier2=${useTier2}`, { method: "POST" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
