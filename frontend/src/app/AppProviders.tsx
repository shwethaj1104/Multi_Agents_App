import type { PropsWithChildren } from "react";
import { Provider } from "react-redux";
import { store } from "./store";

/** Provide the shared Redux store to both separately launched application variants. */
export function AppProviders({ children }: PropsWithChildren) {
  return <Provider store={store}>{children}</Provider>;
}
