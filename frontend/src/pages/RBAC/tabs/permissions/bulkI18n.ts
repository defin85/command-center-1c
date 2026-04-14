import type { useRbacTranslation } from '../../../../i18n'

type Translate = ReturnType<typeof useRbacTranslation>['t']

export const createClusterBulkI18n = (t: Translate) => ({
  title: t(($) => $.permissions.bulk.clusters.title),
  tabGrant: t(($) => $.permissions.bulk.clusters.tabGrant),
  tabRevoke: t(($) => $.permissions.bulk.clusters.tabRevoke),
  confirmGrantTitle: t(($) => $.permissions.bulk.clusters.confirmGrantTitle),
  confirmRevokeTitle: t(($) => $.permissions.bulk.clusters.confirmRevokeTitle),
  applyText: t(($) => $.permissions.bulk.clusters.applyText),
  cancelText: t(($) => $.permissions.bulk.clusters.cancelText),
  roleLabel: t(($) => $.permissions.bulk.clusters.roleLabel),
  levelLabel: t(($) => $.permissions.bulk.clusters.levelLabel),
  notesLabel: t(($) => $.permissions.bulk.clusters.notesLabel),
  countLabel: t(($) => $.permissions.bulk.clusters.countLabel),
  exampleLabel: t(($) => $.permissions.bulk.clusters.exampleLabel),
  rolePlaceholder: t(($) => $.permissions.bulk.clusters.rolePlaceholder),
  notesPlaceholder: t(($) => $.permissions.bulk.clusters.notesPlaceholder),
  reasonPlaceholder: t(($) => $.permissions.bulk.clusters.reasonPlaceholder),
  idsPlaceholder: t(($) => $.permissions.bulk.clusters.idsPlaceholder),
  grantButton: t(($) => $.permissions.bulk.clusters.grantButton),
  revokeButton: t(($) => $.permissions.bulk.clusters.revokeButton),
  idsRequiredMessage: t(($) => $.permissions.bulk.clusters.idsRequiredMessage),
  roleRequiredMessage: t(($) => $.permissions.bulk.clusters.roleRequiredMessage),
  reasonRequiredMessage: t(($) => $.permissions.bulk.clusters.reasonRequiredMessage),
  grantSuccessMessage: (result: { created: number; updated: number; skipped: number }) => (
    t(($) => $.permissions.bulk.clusters.grantSuccessMessage, {
      created: String(result.created),
      updated: String(result.updated),
      skipped: String(result.skipped),
    })
  ),
  revokeSuccessMessage: (result: { deleted: number; skipped: number }) => (
    t(($) => $.permissions.bulk.clusters.revokeSuccessMessage, {
      deleted: String(result.deleted),
      skipped: String(result.skipped),
    })
  ),
  grantFailedMessage: t(($) => $.permissions.bulk.clusters.grantFailedMessage),
  revokeFailedMessage: t(($) => $.permissions.bulk.clusters.revokeFailedMessage),
}) as const

export const createDatabaseBulkI18n = (t: Translate) => ({
  title: t(($) => $.permissions.bulk.databases.title),
  tabGrant: t(($) => $.permissions.bulk.databases.tabGrant),
  tabRevoke: t(($) => $.permissions.bulk.databases.tabRevoke),
  confirmGrantTitle: t(($) => $.permissions.bulk.databases.confirmGrantTitle),
  confirmRevokeTitle: t(($) => $.permissions.bulk.databases.confirmRevokeTitle),
  applyText: t(($) => $.permissions.bulk.databases.applyText),
  cancelText: t(($) => $.permissions.bulk.databases.cancelText),
  roleLabel: t(($) => $.permissions.bulk.databases.roleLabel),
  levelLabel: t(($) => $.permissions.bulk.databases.levelLabel),
  notesLabel: t(($) => $.permissions.bulk.databases.notesLabel),
  countLabel: t(($) => $.permissions.bulk.databases.countLabel),
  exampleLabel: t(($) => $.permissions.bulk.databases.exampleLabel),
  rolePlaceholder: t(($) => $.permissions.bulk.databases.rolePlaceholder),
  notesPlaceholder: t(($) => $.permissions.bulk.databases.notesPlaceholder),
  reasonPlaceholder: t(($) => $.permissions.bulk.databases.reasonPlaceholder),
  idsPlaceholder: t(($) => $.permissions.bulk.databases.idsPlaceholder),
  grantButton: t(($) => $.permissions.bulk.databases.grantButton),
  revokeButton: t(($) => $.permissions.bulk.databases.revokeButton),
  idsRequiredMessage: t(($) => $.permissions.bulk.databases.idsRequiredMessage),
  roleRequiredMessage: t(($) => $.permissions.bulk.databases.roleRequiredMessage),
  reasonRequiredMessage: t(($) => $.permissions.bulk.databases.reasonRequiredMessage),
  grantSuccessMessage: (result: { created: number; updated: number; skipped: number }) => (
    t(($) => $.permissions.bulk.databases.grantSuccessMessage, {
      created: String(result.created),
      updated: String(result.updated),
      skipped: String(result.skipped),
    })
  ),
  revokeSuccessMessage: (result: { deleted: number; skipped: number }) => (
    t(($) => $.permissions.bulk.databases.revokeSuccessMessage, {
      deleted: String(result.deleted),
      skipped: String(result.skipped),
    })
  ),
  grantFailedMessage: t(($) => $.permissions.bulk.databases.grantFailedMessage),
  revokeFailedMessage: t(($) => $.permissions.bulk.databases.revokeFailedMessage),
}) as const
