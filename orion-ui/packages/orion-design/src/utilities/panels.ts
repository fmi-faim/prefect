import { Component, InjectionKey } from 'vue'

// any because its a generic constructor
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type InstanceOfComponent = Component & { new (...args: any): any }
export type ShowPanel = <T extends InstanceOfComponent>(component: T, props: InstanceType<T>['$props']) => void

export const showPanelKey: InjectionKey<ShowPanel> = Symbol()