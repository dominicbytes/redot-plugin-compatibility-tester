using Godot;

public partial class Main : Node
{
    public override void _Ready()
    {
        GD.Print("REDOT_COMPAT_DOTNET_OK");
        GetTree().Quit();
    }
}
