package odata

import (
	"testing"
	"time"

	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"
)

func TestBuildEntityURL(t *testing.T) {
	tests := []struct {
		name     string
		baseURL  string
		entity   string
		entityID string
		want     string
	}{
		{
			name:     "without entity ID",
			baseURL:  "http://server/db/odata/standard.odata",
			entity:   "Catalog_Users",
			entityID: "",
			want:     "http://server/db/odata/standard.odata/Catalog_Users",
		},
		{
			name:     "with entity ID",
			baseURL:  "http://server/db/odata/standard.odata",
			entity:   "Catalog_Users",
			entityID: "guid'12345678-1234-1234-1234-123456789012'",
			want:     "http://server/db/odata/standard.odata/Catalog_Users(guid'12345678-1234-1234-1234-123456789012')",
		},
		{
			name:     "cyrillic entity name",
			baseURL:  "http://server/db/odata/standard.odata",
			entity:   "Catalog_Контрагенты",
			entityID: "",
			want:     "http://server/db/odata/standard.odata/Catalog_Контрагенты",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := BuildEntityURL(tt.baseURL, tt.entity, tt.entityID)
			if got != tt.want {
				t.Errorf("BuildEntityURL() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestBuildQueryString(t *testing.T) {
	tests := []struct {
		name  string
		query *sharedodata.QueryParams
		want  string
	}{
		{
			name:  "nil query",
			query: nil,
			want:  "",
		},
		{
			name:  "empty query",
			query: &sharedodata.QueryParams{},
			want:  "",
		},
		{
			name: "filter only",
			query: &sharedodata.QueryParams{
				Filter: "Name eq 'Test'",
			},
			want: "%24filter=Name+eq+%27Test%27",
		},
		{
			name: "select only",
			query: &sharedodata.QueryParams{
				Select: []string{"Ref_Key", "Description"},
			},
			want: "%24select=Ref_Key%2CDescription",
		},
		{
			name: "top and skip",
			query: &sharedodata.QueryParams{
				Top:  100,
				Skip: 50,
			},
			want: "%24skip=50&%24top=100",
		},
		{
			name: "full query",
			query: &sharedodata.QueryParams{
				Filter:  "DeletionMark eq false",
				Select:  []string{"Ref_Key", "Description"},
				OrderBy: "Description asc",
				Top:     10,
				Skip:    0,
				Expand:  "Parent",
			},
			want: "%24expand=Parent&%24filter=DeletionMark+eq+false&%24orderby=Description+asc&%24select=Ref_Key%2CDescription&%24top=10",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := BuildQueryString(tt.query)
			if got != tt.want {
				t.Errorf("BuildQueryString() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestFormatGUID(t *testing.T) {
	guid := "12345678-1234-1234-1234-123456789012"
	want := "guid'12345678-1234-1234-1234-123456789012'"
	got := FormatGUID(guid)
	if got != want {
		t.Errorf("FormatGUID() = %v, want %v", got, want)
	}
}

func TestFormatDatetime(t *testing.T) {
	dt := time.Date(2025, 11, 9, 12, 30, 45, 0, time.UTC)
	want := "datetime'2025-11-09T12:30:45'"
	got := FormatDatetime(dt)
	if got != want {
		t.Errorf("FormatDatetime() = %v, want %v", got, want)
	}
}

func TestFormatDate(t *testing.T) {
	dt := time.Date(2025, 11, 9, 12, 30, 45, 0, time.UTC)
	want := "datetime'2025-11-09T00:00:00'"
	got := FormatDate(dt)
	if got != want {
		t.Errorf("FormatDate() = %v, want %v", got, want)
	}
}
