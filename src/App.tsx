import { useCallback, useEffect, useState } from "react"
import { api } from "./api"
import { Creator } from "./components/Creator"
import { Editor } from "./components/Editor"
import type { CampaignDetail, CampaignListItem, Catalog } from "./types"

type Tab = "create" | "edit"

export default function App() {
  const [tab, setTab] = useState<Tab>("create")
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [campaigns, setCampaigns] = useState<CampaignListItem[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [error, setError] = useState("")

  const loadCampaigns = useCallback(() => {
    api<CampaignListItem[]>("/api/campaigns")
      .then(setCampaigns)
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Не удалось загрузить кампании")
      })
  }, [])

  useEffect(() => {
    api<Catalog>("/api/catalog")
      .then(setCatalog)
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Нет связи с Keitaro")
      })
    loadCampaigns()
  }, [loadCampaigns])

  function openCreated(campaign: CampaignDetail) {
    setSelectedId(campaign.id)
    setTab("edit")
    loadCampaigns()
  }

  return (
    <div className="app">
      <header className="top">
        <div>
          <p className="eyebrow">Keitaro</p>
          <h1>Обёртка кампаний</h1>
        </div>
        <nav>
          <button
            type="button"
            className={tab === "create" ? "tab is-on" : "tab"}
            onClick={() => setTab("create")}
          >
            Создать
          </button>
          <button
            type="button"
            className={tab === "edit" ? "tab is-on" : "tab"}
            onClick={() => setTab("edit")}
          >
            Редактор
          </button>
        </nav>
      </header>

      {error && <p className="banner">{error}</p>}
      {!catalog && !error && <p className="empty-state">Загружаем справочники Keitaro…</p>}

      {catalog && tab === "create" && <Creator catalog={catalog} onCreated={openCreated} />}
      {catalog && tab === "edit" && (
        <Editor
          catalog={catalog}
          campaigns={campaigns}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onCampaignsChange={loadCampaigns}
        />
      )}
    </div>
  )
}
