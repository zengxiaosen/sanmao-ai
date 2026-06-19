package model

import "testing"

func TestChannelInfoScan(t *testing.T) {
	t.Run("scan string json", func(t *testing.T) {
		var info ChannelInfo
		err := info.Scan(`{"is_multi_key":true,"multi_key_size":2}`)
		if err != nil {
			t.Fatalf("expected string JSON to scan, got error: %v", err)
		}
		if !info.IsMultiKey {
			t.Fatalf("expected IsMultiKey to be true")
		}
		if info.MultiKeySize != 2 {
			t.Fatalf("expected MultiKeySize=2, got %d", info.MultiKeySize)
		}
	})

	t.Run("scan bytes json", func(t *testing.T) {
		var info ChannelInfo
		err := info.Scan([]byte(`{"multi_key_polling_index":3}`))
		if err != nil {
			t.Fatalf("expected []byte JSON to scan, got error: %v", err)
		}
		if info.MultiKeyPollingIndex != 3 {
			t.Fatalf("expected MultiKeyPollingIndex=3, got %d", info.MultiKeyPollingIndex)
		}
	})

	t.Run("scan empty values", func(t *testing.T) {
		info := ChannelInfo{IsMultiKey: true, MultiKeySize: 9}
		if err := info.Scan(nil); err != nil {
			t.Fatalf("expected nil scan to succeed, got error: %v", err)
		}
		if info.IsMultiKey || info.MultiKeySize != 0 {
			t.Fatalf("expected nil scan to reset zero value, got %+v", info)
		}

		info = ChannelInfo{IsMultiKey: true, MultiKeySize: 9}
		if err := info.Scan(""); err != nil {
			t.Fatalf("expected empty string scan to succeed, got error: %v", err)
		}
		if info.IsMultiKey || info.MultiKeySize != 0 {
			t.Fatalf("expected empty string scan to reset zero value, got %+v", info)
		}
	})
}
