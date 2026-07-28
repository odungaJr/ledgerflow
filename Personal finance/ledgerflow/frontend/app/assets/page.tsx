"use client";

import { FormEvent, useEffect, useState } from "react";
import { addAssetValue, ApiError, createAsset, deleteAsset, getAssets } from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import type { Asset } from "@/lib/types";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

const ASSET_TYPES: { value: Asset["asset_type"]; label: string }[] = [
  { value: "cash", label: "Cash" },
  { value: "stocks", label: "Stocks / Shares" },
  { value: "bonds", label: "Bonds" },
  { value: "real_estate", label: "Real Estate" },
  { value: "vehicle", label: "Vehicle" },
  { value: "other", label: "Other" },
];

export default function AssetsPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [assetType, setAssetType] = useState<Asset["asset_type"]>("stocks");
  const [quantity, setQuantity] = useState("");
  const [unitValue, setUnitValue] = useState("");
  const [totalValue, setTotalValue] = useState("");
  const [currency, setCurrency] = useState("TZS");
  const [valueDate, setValueDate] = useState(todayIso());
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [updateValue, setUpdateValue] = useState("");
  const [updateDate, setUpdateDate] = useState(todayIso());

  function load() {
    setLoading(true);
    getAssets()
      .then((data) => {
        setAssets(data);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load assets"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  function handleQuantityOrUnitChange(nextQuantity: string, nextUnit: string) {
    const q = Number(nextQuantity);
    const u = Number(nextUnit);
    if (nextQuantity && nextUnit && q > 0 && u > 0) {
      setTotalValue(String(q * u));
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    const total = Number(totalValue);
    if (!name.trim() || !total || total <= 0) {
      setFormError("Enter a name and a current value greater than zero.");
      return;
    }
    setSubmitting(true);
    try {
      await createAsset({
        name: name.trim(),
        asset_type: assetType,
        quantity: quantity ? Number(quantity) : undefined,
        currency,
        value_date: valueDate,
        total_value: total,
        unit_value: unitValue ? Number(unitValue) : undefined,
      });
      setName("");
      setQuantity("");
      setUnitValue("");
      setTotalValue("");
      load();
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Failed to create asset");
    } finally {
      setSubmitting(false);
    }
  }

  function startUpdate(asset: Asset) {
    setUpdatingId(asset.id);
    setUpdateValue(String(asset.current_value ?? ""));
    setUpdateDate(todayIso());
  }

  async function saveUpdate(id: string) {
    const value = Number(updateValue);
    if (!value || value <= 0) return;
    await addAssetValue(id, { value_date: updateDate, total_value: value });
    setUpdatingId(null);
    load();
  }

  async function handleDelete(asset: Asset) {
    if (!confirm(`Delete "${asset.name}"? This removes its full value history.`)) return;
    await deleteAsset(asset.id);
    load();
  }

  const netWorth = assets.reduce((sum, a) => sum + (a.current_value ?? 0), 0);

  return (
    <main className="page">
      <div className="container">
        <div className="pageHeader">
          <h1>Assets</h1>
          <span className="badge neutral">Net worth: {formatMoney(netWorth)}</span>
        </div>

        <form className="form" onSubmit={handleCreate}>
          <h2 className="sectionTitle">Add an asset</h2>
          <div className="formInline">
            <div className="formRow">
              <label htmlFor="asset-name">Name</label>
              <input
                id="asset-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="CRDB Bank shares"
                required
              />
            </div>
            <div className="formRow" style={{ maxWidth: "160px" }}>
              <label htmlFor="asset-type">Type</label>
              <select id="asset-type" value={assetType} onChange={(e) => setAssetType(e.target.value as Asset["asset_type"])}>
                {ASSET_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="formRow" style={{ maxWidth: "120px" }}>
              <label htmlFor="asset-quantity">Quantity</label>
              <input
                id="asset-quantity"
                type="number"
                min="0"
                step="0.0001"
                value={quantity}
                onChange={(e) => {
                  setQuantity(e.target.value);
                  handleQuantityOrUnitChange(e.target.value, unitValue);
                }}
                placeholder="optional"
              />
            </div>
            <div className="formRow" style={{ maxWidth: "140px" }}>
              <label htmlFor="asset-unit-value">Unit value</label>
              <input
                id="asset-unit-value"
                type="number"
                min="0"
                step="0.01"
                value={unitValue}
                onChange={(e) => {
                  setUnitValue(e.target.value);
                  handleQuantityOrUnitChange(quantity, e.target.value);
                }}
                placeholder="optional"
              />
            </div>
            <div className="formRow" style={{ maxWidth: "160px" }}>
              <label htmlFor="asset-total-value">Current value</label>
              <input
                id="asset-total-value"
                type="number"
                min="1"
                step="0.01"
                value={totalValue}
                onChange={(e) => setTotalValue(e.target.value)}
                placeholder="1000000"
                required
              />
            </div>
            <div className="formRow" style={{ maxWidth: "160px" }}>
              <label htmlFor="asset-date">As of</label>
              <input id="asset-date" type="date" value={valueDate} onChange={(e) => setValueDate(e.target.value)} />
            </div>
            <button className="btn" type="submit" disabled={submitting}>
              {submitting ? "Adding…" : "Add asset"}
            </button>
          </div>
          {formError && <div className="alert error">{formError}</div>}
        </form>

        <div className="spacer">
          {loading && <p>Loading…</p>}
          {error && <div className="alert error">{error}</div>}
          {!loading && !error && assets.length === 0 && (
            <div className="empty">No assets yet — add shares, bonds, or anything else you own above.</div>
          )}
          {!loading && assets.length > 0 && (
            <div className="grid">
              {assets.map((asset) => {
                const change = asset.change_amount ?? 0;
                return (
                  <div className="card" key={asset.id}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <p className="statLabel" style={{ margin: 0 }}>
                        {asset.name}
                      </p>
                      <span className="badge neutral">{ASSET_TYPES.find((t) => t.value === asset.asset_type)?.label}</span>
                    </div>

                    <p className={`statValue ${change >= 0 ? "positive" : "negative"}`} style={{ marginTop: "0.4rem" }}>
                      {formatMoney(asset.current_value ?? 0, asset.currency)}
                    </p>
                    <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                      {[
                        change !== 0 && `${change > 0 ? "+" : ""}${formatMoney(change, asset.currency)} since first entry`,
                        asset.quantity != null && `qty ${asset.quantity}`,
                        asset.value_date && `as of ${formatDate(asset.value_date)}`,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>

                    {updatingId === asset.id ? (
                      <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.6rem", flexWrap: "wrap" }}>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={updateValue}
                          onChange={(e) => setUpdateValue(e.target.value)}
                          style={{ maxWidth: "140px" }}
                        />
                        <input
                          type="date"
                          value={updateDate}
                          onChange={(e) => setUpdateDate(e.target.value)}
                          style={{ maxWidth: "160px" }}
                        />
                        <button className="btn btnSmall" onClick={() => saveUpdate(asset.id)}>
                          Save
                        </button>
                        <button className="btn btnSecondary btnSmall" onClick={() => setUpdatingId(null)}>
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.75rem" }}>
                        <button className="btn btnSecondary btnSmall" onClick={() => startUpdate(asset)}>
                          Update value
                        </button>
                        <button className="btn btnDanger btnSmall" onClick={() => handleDelete(asset)}>
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
