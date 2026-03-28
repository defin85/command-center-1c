package poolops

import (
	"fmt"
	"math"
	"strings"
)

type authoritativeRegisterAmount struct {
	sumAbs          float64
	distinctAmounts map[string]float64
	recordTypes     map[string]struct{}
}

func applyAuthoritativeRegisterAmounts(
	factualDocuments []map[string]interface{},
	accountingRows []map[string]interface{},
	informationRows []map[string]interface{},
) []map[string]interface{} {
	if len(factualDocuments) == 0 || len(accountingRows) == 0 {
		return factualDocuments
	}

	documentAliases := buildFactualDocumentAliasIndex(factualDocuments, informationRows)
	if len(documentAliases) == 0 {
		return factualDocuments
	}

	authoritativeAmounts := collectAuthoritativeRegisterAmounts(accountingRows, documentAliases)
	if len(authoritativeAmounts) == 0 {
		return factualDocuments
	}

	filteredDocuments := make([]map[string]interface{}, 0, len(authoritativeAmounts))
	for _, document := range factualDocuments {
		sourceDocumentRef := strings.TrimSpace(fmt.Sprintf("%v", document["source_document_ref"]))
		if sourceDocumentRef == "" {
			continue
		}
		amountWithVAT, ok := authoritativeAmounts[sourceDocumentRef]
		if !ok {
			continue
		}
		applyAuthoritativeAmountToDocument(document, amountWithVAT)
		filteredDocuments = append(filteredDocuments, document)
	}

	return filteredDocuments
}

func buildFactualDocumentAliasIndex(
	factualDocuments []map[string]interface{},
	informationRows []map[string]interface{},
) map[string]string {
	aliases := make(map[string]string, len(factualDocuments)*2)
	for _, document := range factualDocuments {
		sourceDocumentRef := strings.TrimSpace(fmt.Sprintf("%v", document["source_document_ref"]))
		if sourceDocumentRef == "" {
			continue
		}
		addSourceDocumentAlias(aliases, sourceDocumentRef, sourceDocumentRef)
		if guid := extractSourceDocumentRefGUID(sourceDocumentRef); guid != "" {
			addSourceDocumentAlias(aliases, guid, sourceDocumentRef)
		}
	}

	for _, row := range informationRows {
		sourceDocumentRef := resolveSourceDocumentRefAlias(
			firstNonEmpty(
				row["Документ"],
				row["Document"],
				row["source_document_ref"],
				row["document_ref"],
				row["Ref_Key"],
				row["ref_key"],
			),
			aliases,
		)
		if sourceDocumentRef == "" {
			continue
		}
		addSourceDocumentAlias(aliases, sourceDocumentRef, sourceDocumentRef)
		addSourceDocumentAlias(aliases, firstNonEmpty(row["Номер"], row["Number"]), sourceDocumentRef)
	}

	return aliases
}

func collectAuthoritativeRegisterAmounts(
	accountingRows []map[string]interface{},
	documentAliases map[string]string,
) map[string]float64 {
	aggregates := make(map[string]*authoritativeRegisterAmount)
	for _, row := range accountingRows {
		sourceDocumentRef := resolveSourceDocumentRefAlias(
			firstNonEmpty(
				row["Recorder"],
				row["Документ"],
				row["Document"],
				row["source_document_ref"],
				row["document_ref"],
				row["Номер"],
				row["Number"],
			),
			documentAliases,
		)
		if sourceDocumentRef == "" {
			continue
		}

		amount := math.Abs(
			mustParseFloat(
				parseDecimalString(
					firstNonEmpty(
						row["amount_with_vat"],
						row["AmountWithVAT"],
						row["Amount"],
						row["Сумма"],
					),
				),
			),
		)
		if amount == 0 {
			continue
		}

		aggregate := aggregates[sourceDocumentRef]
		if aggregate == nil {
			aggregate = &authoritativeRegisterAmount{
				distinctAmounts: make(map[string]float64),
				recordTypes:     make(map[string]struct{}),
			}
			aggregates[sourceDocumentRef] = aggregate
		}
		aggregate.sumAbs += amount
		aggregate.distinctAmounts[parseDecimalString(amount)] = amount
		if recordType := normalizeSourceDocumentAlias(firstNonEmpty(row["RecordType"], row["record_type"])); recordType != "" {
			aggregate.recordTypes[recordType] = struct{}{}
		}
	}

	result := make(map[string]float64, len(aggregates))
	for sourceDocumentRef, aggregate := range aggregates {
		if aggregate == nil || aggregate.sumAbs == 0 {
			continue
		}
		if len(aggregate.recordTypes) > 1 && len(aggregate.distinctAmounts) == 1 {
			for _, amount := range aggregate.distinctAmounts {
				result[sourceDocumentRef] = amount
			}
			continue
		}
		result[sourceDocumentRef] = aggregate.sumAbs
	}
	return result
}

func applyAuthoritativeAmountToDocument(document map[string]interface{}, amountWithVAT float64) {
	if document == nil || amountWithVAT <= 0 {
		return
	}

	currentAmountWithVAT := math.Abs(mustParseFloat(parseDecimalString(document["amount_with_vat"])))
	currentVATAmount := math.Abs(mustParseFloat(parseDecimalString(document["vat_amount"])))

	nextAmountWithVAT := parseDecimalString(amountWithVAT)
	if currentAmountWithVAT <= 0 {
		document["amount_with_vat"] = nextAmountWithVAT
		document["amount_without_vat"] = nextAmountWithVAT
		document["vat_amount"] = "0.00"
		return
	}

	nextVATAmount := math.Abs(currentVATAmount * (amountWithVAT / currentAmountWithVAT))
	if nextVATAmount > amountWithVAT {
		nextVATAmount = amountWithVAT
	}
	nextAmountWithoutVAT := math.Max(amountWithVAT-nextVATAmount, 0)

	document["amount_with_vat"] = nextAmountWithVAT
	document["amount_without_vat"] = parseDecimalString(nextAmountWithoutVAT)
	document["vat_amount"] = parseDecimalString(nextVATAmount)
}

func addSourceDocumentAlias(aliases map[string]string, rawAlias, sourceDocumentRef string) {
	alias := normalizeSourceDocumentAlias(rawAlias)
	if alias == "" || strings.TrimSpace(sourceDocumentRef) == "" {
		return
	}
	aliases[alias] = sourceDocumentRef
}

func resolveSourceDocumentRefAlias(rawAlias string, aliases map[string]string) string {
	alias := normalizeSourceDocumentAlias(rawAlias)
	if alias == "" {
		return ""
	}
	if sourceDocumentRef, ok := aliases[alias]; ok {
		return sourceDocumentRef
	}
	if guid := extractSourceDocumentRefGUID(alias); guid != "" {
		if sourceDocumentRef, ok := aliases[guid]; ok {
			return sourceDocumentRef
		}
	}
	if strings.Contains(alias, "(guid'") {
		return rawAlias
	}
	return ""
}

func normalizeSourceDocumentAlias(rawAlias string) string {
	alias := strings.TrimSpace(rawAlias)
	if alias == "" {
		return ""
	}
	alias = strings.TrimPrefix(alias, "StandardODATA.")
	alias = strings.TrimPrefix(alias, "standardodata.")
	alias = strings.TrimPrefix(alias, "guid'")
	alias = strings.TrimSuffix(alias, "'")
	return strings.ToLower(strings.TrimSpace(alias))
}

func extractSourceDocumentRefGUID(sourceDocumentRef string) string {
	normalized := strings.TrimSpace(sourceDocumentRef)
	if normalized == "" {
		return ""
	}
	if !strings.Contains(strings.ToLower(normalized), "(guid'") {
		return normalizeSourceDocumentAlias(normalized)
	}
	start := strings.Index(strings.ToLower(normalized), "(guid'")
	if start < 0 {
		return ""
	}
	start += len("(guid'")
	end := strings.Index(normalized[start:], "'")
	if end < 0 {
		return ""
	}
	return normalizeSourceDocumentAlias(normalized[start : start+end])
}
