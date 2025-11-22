import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { supabase } from "./lib/supabase";

type Status = "IDLE" | "LISTENING" | "THREAT_DETECTED";

export default function App() {
  const [status, setStatus] = useState<Status>("IDLE");
  const [transcript, setTranscript] = useState("");

  const channel = supabase.channel("live_call");
  channel
    .on("broadcast", { event: "transcript" }, (data) => {
      setTranscript(data.payload.text);
    })
    .subscribe();

  useEffect(() => {
    const fetchState = async () => {
      const { data } = await supabase.from("active_calls").select("*").eq("id", 1).single();

      if (data) {
        setStatus(data.status);
        console.log(data);
      }
    };

    fetchState();
  }, []);

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
    backgroundColor: "#fff",
    alignItems: "center",
    justifyContent: "center",
  },
});
