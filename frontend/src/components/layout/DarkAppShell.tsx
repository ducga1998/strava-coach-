import { ConfigProvider } from "antd"
import type { ReactNode } from "react"
import { useDarkPageChrome } from "../../hooks/useDarkPageChrome"
import { antdAppDark } from "../../theme/antdAppDark"
import AppChromeHeader from "./AppChromeHeader"

export default function DarkAppShell({ children }: { children: ReactNode }) {
  useDarkPageChrome()
  return (
    <ConfigProvider theme={antdAppDark}>
      <div className="min-h-screen bg-[#050505] bg-brand-void font-sans text-neutral-50 antialiased">
        <AppChromeHeader />
        <div className="pt-14">{children}</div>
      </div>
    </ConfigProvider>
  )
}
