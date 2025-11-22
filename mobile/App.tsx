import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { supabase } from "./lib/supabase";

type Status = "IDLE" | "RINGING" | "ANALYZING" | "THREAT_DETECTED";

export default function App() {
  const [status, setStatus] = useState<Status>("IDLE");
  const [transcript, setTranscript] = useState("");

  useEffect(() => {
    const liveCallChannel = supabase.channel("live_call");
    liveCallChannel
      .on("broadcast", { event: "transcript" }, (data) => {
        setTranscript(data.payload.text);
      })
      .subscribe();

    const statusChannel = supabase
      .channel("public:active_calls")
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "active_calls",
        },
        (payload) => {
          const newData = payload.new;
          setStatus(newData.status);
          if (newData.transcript) setTranscript(newData.transcript);
        },
      )
      .subscribe();

    return () => {
      supabase.removeChannel(liveCallChannel);
      supabase.removeChannel(statusChannel);
    };
  }, []);

  // useEffect(() => {
  //   const fetchState = async () => {
  //     const { data } = await supabase.from("active_calls").select("*").eq("id", 1).single();

  //     if (data) {
  //       setStatus(data.status);
  //       console.log(data);
  //     }
  //   };

  //   fetchState();
  // }, []);

  if (status === "IDLE") {
    return (
      <View style={[styles.container, { backgroundColor: "#f0fdf4" }]}>
        <View style={styles.shieldCircle}>
          <Text style={{ fontSize: 50 }}>🛡️</Text>
        </View>
        <Text style={styles.title}>Arghus</Text>
        <Text style={styles.subtitle}>Monitoring incoming calls...</Text>
      </View>
    );
  }

  if (status === "RINGING" || status === "ANALYZING") {
    return (
      <View style={[styles.container, { backgroundColor: "#111827" }]}>
        <Text style={[styles.title, { color: "white" }]}>Call Intercepted</Text>
        <Text style={[styles.subtitle, { color: "#bcc5d6ff" }]}>
          {status === "RINGING" ? "Connecting ..." : "Analyzing..."}
        </Text>

        <View style={styles.transcriptBox}>
          <Text style={styles.transcriptLabel}>LIVE TRANSCRIPT:</Text>
          <Text style={styles.transcriptText}>{transcript}</Text>
        </View>

        {/* <View style={styles.loadingBar} /> */}
      </View>
    );
  }
  if (status === "THREAT_DETECTED") {
    return (
      <View style={[styles.container, { backgroundColor: "#5b1d1dff" }]}>
        <Text style={[styles.title, { color: "white", marginTop: 50 }]}>⚠️ Possible Scam</Text>

        <View style={styles.card}>
          <Text style={styles.cardLabel}>THREAT ANALYSIS:</Text>
          {/* <Text style={styles.cardValue}>Confidence: {threatData?.score || 75}%</Text> */}
          <Text style={styles.cardValue}>Reason: Financial Urgency + Voice Mismatch</Text>
        </View>

        <ScrollView style={styles.transcriptScroll}>
          <Text style={{ color: "#ccc" }}>... {transcript}</Text>
        </ScrollView>

        <View style={styles.actionArea}>
          <Text style={{ color: "white", marginBottom: 10, textAlign: "center" }}>Recommended Action:</Text>
          {/* <TouchableOpacity style={styles.button} onPress={sendInjectAction}>
            <Text style={styles.buttonText}>INJECT CHALLENGE QUESTION</Text>
          </TouchableOpacity>
          <Text style={{ color: "white", marginTop: 10, textAlign: "center", fontSize: 12 }}>
            "{threatData?.question || "Ask Secret Question"}"
          </Text> */}
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text>{status}</Text>
      <Text>{transcript}</Text>
      <StatusBar style="auto" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingHorizontal: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  shieldCircle: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: "#dcfce7",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 20,
  },
  title: { fontSize: 24, fontWeight: "bold", marginBottom: 10 },
  subtitle: { fontSize: 16, color: "#6b7280" },
  transcriptBox: {
    width: "100%",
    marginTop: 40,
    padding: 15,
    backgroundColor: "#1f2937",
    borderRadius: 10,
    minHeight: 200,
  },
  transcriptLabel: { color: "#4ade80", fontSize: 10, fontWeight: "bold", marginBottom: 5 },
  transcriptText: { color: "white", fontSize: 16, lineHeight: 24 },
  card: { width: "100%", backgroundColor: "rgba(0,0,0,0.3)", padding: 15, borderRadius: 10, marginVertical: 20 },
  cardLabel: { color: "#fca5a5", fontSize: 12, fontWeight: "bold" },
  cardValue: { color: "white", fontSize: 16, fontWeight: "bold", marginTop: 5 },
  button: { backgroundColor: "white", padding: 15, borderRadius: 30, width: "100%", alignItems: "center" },
  buttonText: { color: "#7f1d1d", fontWeight: "bold" },
  transcriptScroll: { maxHeight: 150, width: "100%", marginBottom: 20 },
  actionArea: { width: "100%", position: "absolute", bottom: 50 },
});
