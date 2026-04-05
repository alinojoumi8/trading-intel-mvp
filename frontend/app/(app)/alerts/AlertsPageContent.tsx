"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getAlertRules,
  createAlertRule,
  deleteAlertRule,
  testAlertRule,
  updateAlertRule,
  getAlertLogs,
  acknowledgeAlertLog,
  AlertRule,
  AlertLog,
  CreateAlertRuleData,
} from "@/lib/api";

const CONDITION_TYPES = [
  { value: "regime_change", label: "Regime Change", desc: "Triggered when regime changes for an instrument" },
  { value: "setup_generated", label: "Setup Generated", desc: "Triggered when a new trade setup is created" },
  { value: "cot_change", label: "COT Change", desc: "Triggered when COT net position changes significantly" },
  { value: "price_cross", label: "Price Cross", desc: "Triggered when price crosses a level" },
  { value: "rsi_level", label: "RSI Level", desc: "Triggered when RSI enters overbought/oversold" },
];

const INSTRUMENTS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "XAUUSD", "BTCUSD"];

// ─── Color helpers ──────────────────────────────────────────────────────────

function conditionBadgeColor(type: string): string {
  switch (type) {
    case "regime_change": return "bg-blue-900/50 text-blue-400 border-blue-700";
    case "setup_generated": return "bg-green-900/50 text-green-400 border-green-700";
    case "cot_change": return "bg-purple-900/50 text-purple-400 border-purple-700";
    case "price_cross": return "bg-yellow-900/50 text-yellow-400 border-yellow-700";
    case "rsi_level": return "bg-orange-900/50 text-orange-400 border-orange-700";
    default: return "bg-zinc-800/50 text-zinc-400 border-zinc-700";
  }
}

function statusColor(enabled: boolean): string {
  return enabled ? "text-green-400" : "text-zinc-500";
}

// ─── Condition Params Form ─────────────────────────────────────────────────

interface ConditionParamsFormProps {
  conditionType: string;
  params: Record<string, unknown>;
  onChange: (params: Record<string, unknown>) => void;
}

function ConditionParamsForm({ conditionType, params, onChange }: ConditionParamsFormProps) {
  const update = (key: string, value: unknown) => {
    onChange({ ...params, [key]: value });
  };

  if (conditionType === "setup_generated") {
    return (
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-zinc-500 text-xs mb-1">Min R:R Ratio</label>
          <input
            type="number"
            step="0.1"
            min="0"
            value={(params.min_rr as number) ?? ""}
            onChange={e => update("min_rr", parseFloat(e.target.value) || 0)}
            className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-white text-sm"
            placeholder="1.5"
          />
        </div>
        <div>
          <label className="block text-zinc-500 text-xs mb-1">Min Confidence %</label>
          <input
            type="number"
            step="5"
            min="0"
            max="100"
            value={(params.min_confidence as number) ?? ""}
            onChange={e => update("min_confidence", parseInt(e.target.value) || 0)}
            className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-white text-sm"
            placeholder="60"
          />
        </div>
      </div>
    );
  }

  if (conditionType === "cot_change") {
    return (
      <div>
        <label className="block text-zinc-500 text-xs mb-1">Threshold % (net position change)</label>
        <input
          type="number"
          step="5"
          min="1"
          max="100"
          value={(params.threshold_pct as number) ?? 20}
          onChange={e => update("threshold_pct", parseInt(e.target.value) || 20)}
          className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-white text-sm"
          placeholder="20"
        />
      </div>
    );
  }

  if (conditionType === "price_cross") {
    return (
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-zinc-500 text-xs mb-1">Price Level</label>
          <input
            type="number"
            step="0.0001"
            value={(params.level as number) ?? ""}
            onChange={e => update("level", parseFloat(e.target.value) || 0)}
            className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-white text-sm"
            placeholder="1.0850"
          />
        </div>
        <div>
          <label className="block text-zinc-500 text-xs mb-1">Direction</label>
          <select
            value={(params.direction as string) ?? "cross"}
            onChange={e => update("direction", e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-white text-sm"
          >
            <option value="cross">Cross (both)</option>
            <option value="above">Above (breakout)</option>
            <option value="below">Below (breakdown)</option>
          </select>
        </div>
      </div>
    );
  }

  if (conditionType === "rsi_level") {
    return (
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-zinc-500 text-xs mb-1">Level (RSI value)</label>
          <input
            type="number"
            step="1"
            min="50"
            max="90"
            value={(params.level as number) ?? 70}
            onChange={e => update("level", parseInt(e.target.value) || 70)}
            className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-white text-sm"
            placeholder="70"
          />
        </div>
        <div>
          <label className="block text-zinc-500 text-xs mb-1">Zone</label>
          <select
            value={(params.zone as string) ?? "overbought"}
            onChange={e => update("zone", e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-white text-sm"
          >
            <option value="overbought">Overbought ( RSI {'>='} level)</option>
            <option value="oversold">Oversold ( RSI {'<='} 100-level)</option>
            <option value="any">Any (either extreme)</option>
          </select>
        </div>
      </div>
    );
  }

  // regime_change - no params needed
  return (
    <p className="text-zinc-500 text-xs italic">No additional parameters required</p>
  );
}

// ─── Create Rule Form ──────────────────────────────────────────────────────

interface CreateRuleFormProps {
  onCreated: () => void;
  onCancel: () => void;
}

function CreateRuleForm({ onCreated, onCancel }: CreateRuleFormProps) {
  const [name, setName] = useState("");
  const [instrument, setInstrument] = useState<string | null>(null);
  const [conditionType, setConditionType] = useState("regime_change");
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [notifyVia, setNotifyVia] = useState("telegram");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const data: CreateAlertRuleData = {
        name: name.trim(),
        instrument: instrument || null,
        condition_type: conditionType,
        condition_params: params,
        enabled: true,
        notify_via: notifyVia,
      };
      await createAlertRule(data);
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create rule");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="border border-zinc-700 rounded-lg p-4 bg-zinc-950 space-y-4">
      <h3 className="text-white font-semibold text-sm">Create New Alert Rule</h3>

      <div>
        <label className="block text-zinc-500 text-xs mb-1">Alert Name *</label>
        <input
          type="text"
          value={name}
          onChange={e => setName(e.target.value)}
          className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-white text-sm"
          placeholder="e.g., EUR/USD Regime Change Alert"
          required
        />
      </div>

      <div>
        <label className="block text-zinc-500 text-xs mb-1">Instrument</label>
        <select
          value={instrument ?? ""}
          onChange={e => setInstrument(e.target.value || null)}
          className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-white text-sm"
        >
          <option value="">All Instruments</option>
          {INSTRUMENTS.map(inst => (
            <option key={inst} value={inst}>{inst}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-zinc-500 text-xs mb-1">Condition Type</label>
        <select
          value={conditionType}
          onChange={e => {
            setConditionType(e.target.value);
            setParams({});
          }}
          className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-white text-sm"
        >
          {CONDITION_TYPES.map(ct => (
            <option key={ct.value} value={ct.value}>{ct.label}</option>
          ))}
        </select>
        <p className="text-zinc-600 text-[10px] mt-1">
          {CONDITION_TYPES.find(ct => ct.value === conditionType)?.desc}
        </p>
      </div>

      <div>
        <label className="block text-zinc-500 text-xs mb-2">Condition Parameters</label>
        <ConditionParamsForm conditionType={conditionType} params={params} onChange={setParams} />
      </div>

      <div>
        <label className="block text-zinc-500 text-xs mb-1">Notify Via</label>
        <select
          value={notifyVia}
          onChange={e => setNotifyVia(e.target.value)}
          className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-white text-sm"
        >
          <option value="telegram">Telegram</option>
          <option value="both">Telegram + Other</option>
        </select>
      </div>

      {error && (
        <div className="px-3 py-2 bg-red-900/30 border border-red-800 rounded text-red-400 text-xs">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={submitting || !name.trim()}
          className="px-4 py-1.5 bg-green-600 hover:bg-green-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white text-xs font-medium rounded transition-colors"
        >
          {submitting ? "Creating..." : "Create Alert Rule"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs rounded transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

// ─── Alert Rule Card ───────────────────────────────────────────────────────

interface AlertRuleCardProps {
  rule: AlertRule;
  onToggle: (rule: AlertRule) => void;
  onDelete: (rule: AlertRule) => void;
  onTest: (rule: AlertRule) => void;
}

function AlertRuleCard({ rule, onToggle, onDelete, onTest }: AlertRuleCardProps) {
  return (
    <div className="border border-zinc-800 rounded-lg p-4 bg-zinc-950 hover:border-zinc-700 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="text-white font-medium text-sm">{rule.name}</h4>
            <span className={`text-[10px] px-2 py-0.5 rounded border ${conditionBadgeColor(rule.condition_type)}`}>
              {rule.condition_type}
            </span>
          </div>
          <p className="text-zinc-500 text-xs">
            Instrument: {rule.instrument || "All"} · Notify: {rule.notify_via}
          </p>
          {rule.last_triggered && (
            <p className="text-zinc-600 text-[10px] mt-1">
              Last triggered: {new Date(rule.last_triggered).toLocaleString()}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 ml-4">
          {/* Toggle */}
          <button
            onClick={() => onToggle(rule)}
            className={`w-8 h-4 rounded-full transition-colors relative ${
              rule.enabled ? "bg-green-600" : "bg-zinc-700"
            }`}
            title={rule.enabled ? "Disable" : "Enable"}
          >
            <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${
              rule.enabled ? "left-4" : "left-0.5"
            }`} />
          </button>
          {/* Test */}
          <button
            onClick={() => onTest(rule)}
            className="text-zinc-500 hover:text-blue-400 text-xs px-2 py-1 border border-zinc-700 hover:border-blue-600 rounded transition-colors"
            title="Send test notification"
          >
            Test
          </button>
          {/* Delete */}
          <button
            onClick={() => onDelete(rule)}
            className="text-zinc-500 hover:text-red-400 text-xs px-2 py-1 border border-zinc-700 hover:border-red-600 rounded transition-colors"
            title="Delete rule"
          >
            ×
          </button>
        </div>
      </div>

      {/* Condition params summary */}
      {Object.keys(rule.condition_params).length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {Object.entries(rule.condition_params).map(([key, val]) => (
            <span key={key} className="text-[10px] px-1.5 py-0.5 bg-zinc-800 text-zinc-400 rounded">
              {key}: {String(val)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Alert Log Item ────────────────────────────────────────────────────────

interface AlertLogItemProps {
  log: AlertLog;
  onAcknowledge: (log: AlertLog) => void;
}

function AlertLogItem({ log, onAcknowledge }: AlertLogItemProps) {
  return (
    <div className={`border rounded-lg p-3 transition-colors ${
      log.acknowledged ? "border-zinc-800 bg-zinc-950/50 opacity-60" : "border-red-900/50 bg-red-950/10"
    }`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {!log.acknowledged && (
            <span className="inline-block w-2 h-2 rounded-full bg-red-500 mb-1 mr-1" />
          )}
          <p className="text-zinc-300 text-xs leading-relaxed whitespace-pre-wrap">
            {log.message}
          </p>
          <p className="text-zinc-600 text-[10px] mt-1">
            {new Date(log.triggered_at).toLocaleString()}
          </p>
        </div>
        {!log.acknowledged && (
          <button
            onClick={() => onAcknowledge(log)}
            className="shrink-0 px-2 py-1 text-[10px] border border-zinc-700 hover:border-zinc-500 text-zinc-400 hover:text-white rounded transition-colors"
          >
            ACK
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Main Content ──────────────────────────────────────────────────────────

export default function AlertsPageContent() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [logs, setLogs] = useState<AlertLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [filter, setFilter] = useState<"all" | "enabled" | "disabled">("all");
  const [logFilter, setLogFilter] = useState<"all" | "unack">("unack");
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [rulesData, logsData] = await Promise.all([
        getAlertRules(),
        getAlertLogs({ limit: 50 }),
      ]);
      setRules(rulesData);
      setLogs(logsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const showMessage = (msg: string) => {
    setActionMsg(msg);
    setTimeout(() => setActionMsg(null), 3000);
  };

  const handleToggle = async (rule: AlertRule) => {
    try {
      await updateAlertRule(rule.id, { enabled: !rule.enabled });
      await loadData();
      showMessage(`Alert ${rule.enabled ? "disabled" : "enabled"}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update rule");
    }
  };

  const handleDelete = async (rule: AlertRule) => {
    if (!confirm(`Delete alert rule "${rule.name}"?`)) return;
    try {
      await deleteAlertRule(rule.id);
      await loadData();
      showMessage("Alert rule deleted");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete rule");
    }
  };

  const handleTest = async (rule: AlertRule) => {
    try {
      await testAlertRule(rule.id);
      showMessage("Test notification sent to Telegram");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send test. Check Telegram config.");
    }
  };

  const handleAcknowledge = async (log: AlertLog) => {
    try {
      await acknowledgeAlertLog(log.id);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to acknowledge");
    }
  };

  const filteredRules = rules.filter(rule => {
    if (filter === "enabled") return rule.enabled;
    if (filter === "disabled") return !rule.enabled;
    return true;
  });

  const filteredLogs = logs.filter(log => {
    if (logFilter === "unack") return !log.acknowledged;
    return true;
  });

  const enabledCount = rules.filter(r => r.enabled).length;
  const unackCount = logs.filter(l => !l.acknowledged).length;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-white font-bold text-xl tracking-tight">ALERTS</h1>
            <p className="text-zinc-500 text-xs mt-0.5">
              Market event notifications via Telegram
            </p>
          </div>
          <div className="flex gap-4 text-xs">
            <div className="text-center">
              <p className="text-white text-lg font-bold">{rules.length}</p>
              <p className="text-zinc-600">Total Rules</p>
            </div>
            <div className="text-center">
              <p className="text-green-400 text-lg font-bold">{enabledCount}</p>
              <p className="text-zinc-600">Active</p>
            </div>
            <div className="text-center">
              <p className="text-red-400 text-lg font-bold">{unackCount}</p>
              <p className="text-zinc-600">Unack'd</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-xs font-medium rounded transition-colors"
          >
            <span className="text-lg">+</span>
            New Alert Rule
          </button>

          <div className="flex items-center gap-1 ml-auto">
            <button
              onClick={() => setFilter("all")}
              className={`px-3 py-1 text-xs rounded transition-colors ${
                filter === "all" ? "bg-zinc-700 text-white" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
              }`}
            >
              All
            </button>
            <button
              onClick={() => setFilter("enabled")}
              className={`px-3 py-1 text-xs rounded transition-colors ${
                filter === "enabled" ? "bg-green-900/50 text-green-400" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
              }`}
            >
              Enabled
            </button>
            <button
              onClick={() => setFilter("disabled")}
              className={`px-3 py-1 text-xs rounded transition-colors ${
                filter === "disabled" ? "bg-zinc-700 text-white" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
              }`}
            >
              Disabled
            </button>
          </div>
        </div>
      </div>

      {/* Action message */}
      {actionMsg && (
        <div className="mx-6 mt-4 px-4 py-2 bg-green-900/30 border border-green-800 rounded text-green-400 text-xs">
          {actionMsg}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mx-6 mt-4 px-4 py-2 bg-red-900/30 border border-red-800 rounded text-red-400 text-xs">
          {error}
        </div>
      )}

      {/* Create form */}
      {showCreateForm && (
        <div className="mx-6 mt-4">
          <CreateRuleForm
            onCreated={() => {
              setShowCreateForm(false);
              loadData();
            }}
            onCancel={() => setShowCreateForm(false)}
          />
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <p className="text-zinc-500 text-sm">Loading...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Alert Rules */}
            <div>
              <h2 className="text-white font-semibold text-sm mb-3">
                Alert Rules ({filteredRules.length})
              </h2>
              {filteredRules.length === 0 ? (
                <div className="border border-zinc-800 rounded-lg p-8 text-center">
                  <p className="text-zinc-500 text-sm">No alert rules yet</p>
                  <p className="text-zinc-600 text-xs mt-1">Create one to get started</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {filteredRules.map(rule => (
                    <AlertRuleCard
                      key={rule.id}
                      rule={rule}
                      onToggle={handleToggle}
                      onDelete={handleDelete}
                      onTest={handleTest}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Alert Logs */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-white font-semibold text-sm">
                  Alert Logs ({filteredLogs.length})
                </h2>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setLogFilter("all")}
                    className={`px-2 py-0.5 text-[10px] rounded transition-colors ${
                      logFilter === "all" ? "bg-zinc-700 text-white" : "bg-zinc-800 text-zinc-500 hover:bg-zinc-700"
                    }`}
                  >
                    All
                  </button>
                  <button
                    onClick={() => setLogFilter("unack")}
                    className={`px-2 py-0.5 text-[10px] rounded transition-colors ${
                      logFilter === "unack" ? "bg-red-900/50 text-red-400" : "bg-zinc-800 text-zinc-500 hover:bg-zinc-700"
                    }`}
                  >
                    Unack
                  </button>
                </div>
              </div>
              {filteredLogs.length === 0 ? (
                <div className="border border-zinc-800 rounded-lg p-8 text-center">
                  <p className="text-zinc-500 text-sm">No alert logs</p>
                  <p className="text-zinc-600 text-xs mt-1">Triggered alerts will appear here</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {filteredLogs.map(log => (
                    <AlertLogItem
                      key={log.id}
                      log={log}
                      onAcknowledge={handleAcknowledge}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
