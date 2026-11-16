package com.plantcraft;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import java.io.InputStreamReader;
import java.io.Reader;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.creativetab.v1.FabricCreativeModeTab;
import net.minecraft.ChatFormatting;
import net.minecraft.core.Registry;
import net.minecraft.core.component.DataComponents;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.CreativeModeTab;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.ItemLore;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.RotatedPillarBlock;
import net.minecraft.world.level.block.SoundType;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.minecraft.world.level.material.PushReaction;

/** Registers every plant listed in plantcraft_plants.json (generated from plants/*.yaml): seeds, growable plant blocks,
 *  saplings that grow into trees, and a creative tab. */
public class PlantCraft implements ModInitializer {
	public static final String MOD_ID = "plantcraft";
	private final List<Item> items = new ArrayList<>();

	private static Identifier id(String path) {
		return Identifier.fromNamespaceAndPath(MOD_ID, path);
	}

	private <T extends Block> T block(String path, Function<ResourceKey<Block>, T> factory) {
		ResourceKey<Block> key = ResourceKey.create(Registries.BLOCK, id(path));
		return Registry.register(BuiltInRegistries.BLOCK, key, factory.apply(key));
	}

	private Item item(String path, Component lore, Function<Item.Properties, Item> factory) {
		ResourceKey<Item> key = ResourceKey.create(Registries.ITEM, id(path));
		Item.Properties props = new Item.Properties().setId(key).useItemDescriptionPrefix();
		if (lore != null) {
			props = props.component(DataComponents.LORE, new ItemLore(List.of(lore)));
		}
		Item registered = Registry.register(BuiltInRegistries.ITEM, key, factory.apply(props));
		items.add(registered);
		return registered;
	}

	private static BlockBehaviour.Properties plantProps(ResourceKey<Block> key) {
		return BlockBehaviour.Properties.of().noCollision().instabreak().sound(SoundType.GRASS)
				.pushReaction(PushReaction.POPPED).setId(key);
	}

	@Override
	public void onInitialize() {
		JsonArray plants;
		try (Reader reader = new InputStreamReader(PlantCraft.class.getResourceAsStream("/plantcraft_plants.json"))) {
			plants = new Gson().fromJson(reader, JsonArray.class);
		} catch (Exception e) {
			throw new RuntimeException("Could not load plantcraft_plants.json", e);
		}
		for (JsonElement element : plants) {
			JsonObject o = element.getAsJsonObject();
			String kind = o.get("kind").getAsString();
			String seedId = o.get("seed_id").getAsString();
			Component latin = Component.literal(o.get("latin").getAsString()).withStyle(ChatFormatting.ITALIC, ChatFormatting.GRAY);
			switch (kind) {
				case "herb" -> {
					int maxAge = o.get("max_age").getAsInt();
					Block plant = block(o.get("id").getAsString(), k -> new PlantBlock(plantProps(k), maxAge));
					item(seedId, latin, p -> new BlockItem(plant, p));
				}
				case "tree" -> {
					JsonObject t = o.getAsJsonObject("tree");
					Block log = block(t.get("log_id").getAsString(),
							k -> new RotatedPillarBlock(BlockBehaviour.Properties.ofFullCopy(Blocks.OAK_LOG).setId(k)));
					Block leaves = block(t.get("leaves_id").getAsString(),
							k -> new Block(BlockBehaviour.Properties.of().strength(0.2F).sound(SoundType.GRASS).noOcclusion().setId(k)));
					TreeGen.Spec spec = new TreeGen.Spec(t.get("height_lo").getAsDouble(), t.get("height_hi").getAsDouble(),
							t.get("tail_hi").getAsDouble(), t.get("width_lo").getAsDouble(), t.get("width_hi").getAsDouble());
					Block sapling = block(t.get("sapling_id").getAsString(), k -> new TreeSaplingBlock(plantProps(k), spec, log, leaves));
					item(seedId, latin, p -> new BlockItem(sapling, p));
					item(t.get("sapling_id").getAsString(), latin, p -> new BlockItem(sapling, p));
					item(t.get("log_id").getAsString(), null, p -> new BlockItem(log, p.useBlockDescriptionPrefix()));
					item(t.get("leaves_id").getAsString(), null, p -> new BlockItem(leaves, p.useBlockDescriptionPrefix()));
				}
				default -> item(seedId, latin, Item::new);
			}
		}

		CreativeModeTab tab = FabricCreativeModeTab.builder()
				.title(Component.translatable("itemGroup." + MOD_ID))
				.icon(() -> new ItemStack(items.get(0)))
				.displayItems((params, output) -> items.forEach(output::accept))
				.build();
		Registry.register(BuiltInRegistries.CREATIVE_MODE_TAB, ResourceKey.create(Registries.CREATIVE_MODE_TAB, id("plants")), tab);
	}
}
